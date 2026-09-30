# 데이터 분석 및 제어 명령 생성을 담당하는 DataAnalyzer 클래스

import asyncio
import json
import logging
from rich.pretty import pretty_repr
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)
from nupf.models.notification_data import NotificationData

from .data_store import NotificationDataStore
from .decide_wlan_gnb2_rule import (
    apply_qos_policy,
    build_15f_cell_power,
    extract_wlan_dl_mbps,
)
from .gnb2_rl_engine import create_decision_engine
from .gnb2_rule_engine import Gnb2RuleEngine
from .websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)


# gNB2 판정은 프로세스 전체에서 하나여야 한다.
# 구독(PCF 의 QOS_POLICY_ASSIST, RICF 의 _CELL_POWER_CTRL)마다 분석기가 따로 돌며
# 각자 엔진 상태를 가지면, 한 판정의 두 절반인 15f(DEEP_SLEEP → RICF)와
# 14_e(NR gNB2 GBR=0 → PCF)가 서로 다른 틱·서로 다른 UPF 샘플로 따로 결정된다.
# 9/30 실측(repPeriod 20s): 15f→14_e 지연 11~30초(평균 16초), 22회 중 4회는 gNB2 가
# 이미 ACTIVE 로 돌아간 뒤에 NR=0 이 나갔고, 두 명령의 일치율은 26% 였다.
# 그래서 엔진은 하나를 공유하고, 어느 분석기의 틱에서든 상태가 정해지면 그 상태를
# 아직 받지 못한 활성 분석기 전부에 같은 순간 내보낸다(각 구독의 sub_id/corrId 로 스탬프).
# 판정 입력도 하나로 모은다 — 구독마다 자기 UPF 스트림(샘플 시각이 서로 다름)만 읽으면,
# 공유 엔진이 틱마다 새 샘플과 옛 샘플을 번갈아 받아 새 상태 → 옛 상태 → 새 상태로 깜빡인다.
_shared_engine: Gnb2RuleEngine | None = None
_active_analyzers: list["DataAnalyzer"] = []
# 마지막 판정에 쓴 UPF 샘플의 timeStamp — 이보다 오래된 샘플로는 다시 판정하지 않는다.
_last_sample_ts: datetime | None = None


def _get_shared_engine() -> Gnb2RuleEngine:
    global _shared_engine
    if _shared_engine is None:
        # NCOF_DECISION_ENGINE(rule|rl) 환경변수에 따라 룰 베이스 또는 RL 정책
        # 엔진을 생성한다 (RL 로드 실패 시 룰로 폴백).
        _shared_engine = create_decision_engine()
    return _shared_engine


def _now_iso_kst() -> str:
    """현재 시각을 ISO 8601 문자열로 반환한다. (로컬 타임존 기준)"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


# timeStamp 가 없는 데이터를 "가장 오래된 것"으로 취급하기 위한 하한값
_MIN_TS = datetime.min.replace(tzinfo=timezone.utc)


class DataAnalyzer:
    """
    구독 데이터의 주기적 분석과 제어 명령 생성을 담당한다.

    SubscriptionHandler 로부터 분석 로직이 분리되어,
    NF 통신(구독/구독해지/통지)과 데이터 분석의 책임이 명확히 구분된다.

    - notif_data_store 에서 원시 데이터를 읽어 RuleEngine 으로 분석
    - 생성된 제어 명령을 notify_callback 을 통해 SubscriptionHandler 로 전달
    - QoS 템플릿을 캐싱하여 디스크 I/O 최소화
    - WebSocket 시각화 메시지 전송
    """

    def __init__(
        self,
        subscription_id: str,
        subscription: NncofEventsSubscription,
        notif_data_store: NotificationDataStore,
        control_data_store: NotificationDataStore,
        notify_callback: Callable[[str, list[dict]], Awaitable[None]],
        qos_template_path: str | Path | None = None,
    ):
        self.subscription_id = subscription_id
        self.subscription = subscription
        self.notif_data_store = notif_data_store
        self.control_data_store = control_data_store
        self._notify_callback = notify_callback

        self.is_running = False
        self._task: asyncio.Task | None = None
        logger.info(
            f"[{subscription_id}]결정 엔진: {type(self.decision_engine).__name__}"
        )
        # 이 구독에 마지막으로 내보낸 gNB2 상태 — 공유 판정 상태와 다를 때만 내보낸다.
        # (늦게 들어온 구독도 다음 틱에 현재 상태를 한 번 받는다)
        self._delivered_state: str | None = None
        self._qos_template: list[dict] | None = None
        self._qos_template_path = Path(
            qos_template_path
            or Path(__file__).parent
            / "14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json"
        )

    @property
    def decision_engine(self) -> Gnb2RuleEngine:
        """프로세스 공유 결정 엔진 (_shared_engine 주석 참조)."""
        return _get_shared_engine()

    def get_source_nf_type(self) -> Literal["PCF", "RICF"] | None:
        if not self.subscription.event_subscriptions:
            return None

        mapping: dict[str, Literal["PCF", "RICF"]] = {
            "QOS_POLICY_ASSIST": "PCF",
            "_CELL_POWER_CTRL": "RICF",
        }
        for sub in self.subscription.event_subscriptions:
            if sub.event in mapping:
                return mapping[sub.event]
        return None

    async def start(self):
        self.is_running = True
        if self not in _active_analyzers:
            _active_analyzers.append(self)
        self._task = asyncio.create_task(self._periodic_process())

    async def stop(self):
        self.is_running = False
        self._leave_active_analyzers()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[{self.subscription_id}] DataAnalyzer 중단됨")

    def _leave_active_analyzers(self) -> None:
        """fan-out 대상에서 빠진다. 마지막 분석기가 빠지면 공유 엔진을 버려,
        다음 구독이 첫 판정부터 새 엔진으로 시작하게 한다 (예전의 분석기별 엔진 재생성과 같은 효과)."""
        global _shared_engine, _last_sample_ts
        self._delivered_state = None
        if self in _active_analyzers:
            _active_analyzers.remove(self)
            if not _active_analyzers:
                _shared_engine = None
                _last_sample_ts = None

    async def _notify_analyzing(self):
        await broadcast_web_message(
            sub_id=self.subscription_id,
            from_node="ncof",
            to_node="ncof",
            msg_type="ANALYZING",
            data="{}",
        )
        await asyncio.sleep(3)
        await broadcast_web_message(
            sub_id=self.subscription_id,
            from_node="ncof",
            to_node="ncof",
            msg_type="ANALYZED",
            data="{}",
        )

    async def _periodic_process(self):
        try:
            await self._periodic_loop()
        finally:
            # 감시 만료 등으로 루프가 끝나면 다른 분석기의 fan-out 대상에서도 빠진다.
            self._leave_active_analyzers()

    async def _periodic_loop(self):
        if self.subscription.evt_req is None:
            return

        period = (
            self.subscription.evt_req.rep_period
            if self.subscription.evt_req.rep_period is not None
            else 60
        )
        mon_dur = self.subscription.evt_req.mon_dur

        try:
            while self.is_running:
                now = datetime.now(timezone.utc)

                if mon_dur and now >= mon_dur:
                    self.is_running = False
                    logger.warning(f"[{self.subscription_id}] 감시 만료")
                    break

                remain = (mon_dur - now).total_seconds() if mon_dur else float("inf")
                if remain <= 0:
                    self.is_running = False
                    logger.warning(f"[{self.subscription_id}] 감시 만료")
                    break

                sleep_time = min(period, remain)
                await asyncio.sleep(sleep_time)

                asyncio.create_task(self._notify_analyzing())

                nf_type = self.get_source_nf_type()
                if nf_type is None:
                    logger.warning("cannot retrieve control type...")
                    continue

                await self._analyze_and_generate(nf_type)


        except asyncio.CancelledError:
            logger.debug(f"[{self.subscription_id}] 분석 태스크 취소됨")

    def _load_qos_template(self) -> list[dict] | None:
        if self._qos_template is not None:
            return self._qos_template

        try:
            with open(self._qos_template_path, "r", encoding="utf-8") as f:
                self._qos_template = json.load(f)
            return self._qos_template
        except FileNotFoundError:
            logger.error(f"템플릿 파일을 찾을 수 없음: {self._qos_template_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return None

    @staticmethod
    def _udum_timestamp(notif: Any) -> datetime | None:
        """USER_DATA_USAGE_MEASURES 항목이 있으면 그중 가장 늦은 timeStamp 를,
        해당 항목이 없으면 None 을 반환한다. (timeStamp 가 비어 있으면 최소값 취급)"""
        if not isinstance(notif, NotificationData):
            return None

        latest: datetime | None = None
        for item in notif.notification_items or []:
            if item is None or item.event_type != "USER_DATA_USAGE_MEASURES":
                continue
            ts = item.time_stamp or _MIN_TS
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if latest is None or ts > latest:
                latest = ts
        return latest

    def _get_wlan_performance_data(self) -> tuple[NotificationData, datetime] | None:
        """
        UPF WLAN 성능 데이터와 그 timeStamp 를 조회한다.

        USER_DATA_USAGE_MEASURES 이벤트 타입의 NotificationData 중 timeStamp 가
        가장 최신인 것을 반환한다. 저장 순서상 첫 번째 것을 고르면, 그 스트림의
        주기 통지가 끊겼을 때 갱신되지 않는 값을 계속 읽어 분석 결과가 고정된다.
        판정이 프로세스 공유이므로 자기 구독뿐 아니라 활성 구독 전부의 store 에서 고른다.
        """
        stores = [a.notif_data_store for a in _active_analyzers]
        if self.notif_data_store not in stores:
            stores.append(self.notif_data_store)

        newest: NotificationData | None = None
        newest_ts: datetime | None = None
        for store in stores:
            for notif in store.get_all().values():
                ts = self._udum_timestamp(notif)
                if ts is None:
                    continue
                if newest_ts is None or ts > newest_ts:
                    newest, newest_ts = notif, ts
        if newest is None or newest_ts is None:
            return None
        return newest, newest_ts

    async def _analyze_and_generate(self, nf_type: str) -> None:
        """이번 틱의 판정을 공유 엔진에 반영하고, 그 상태를 아직 받지 못한 활성 구독
        전부(RICF 15f · PCF 14_e)에 같은 순간 내보낸다. (_shared_engine 주석 참조)"""

        global _last_sample_ts
        sample = self._get_wlan_performance_data()
        if sample is None:
            logger.warning("fail to retrieve wlan performance data...")
            return
        wlan_perf_data, sample_ts = sample

        decision_iso = _now_iso_kst()
        engine = self.decision_engine
        if _last_sample_ts is not None and sample_ts < _last_sample_ts:
            # 직전 판정보다 오래된 샘플(해당 스트림 구독 해지 등) — 옛 값으로 되돌아가지 않도록
            # 다시 판정하지 않고 현재 상태만 유지한다. (같은 샘플 재판정은 결과가 같아 허용)
            logger.info(
                f"[{self.subscription_id}] 직전 판정보다 오래된 UPF 샘플({sample_ts.isoformat()}) — 판정 생략"
            )
            state = engine.last_emitted_state
            if state is None:
                return
        else:
            logger.info(f"RLlib 입력 데이터 추출:")
            try:
                metric = extract_wlan_dl_mbps(wlan_perf_data.to_dict())
                logger.info(f"분석 메트릭 WLAN_DL_MBPS:{metric}")
                logger.info("AI 분석 시작")
                state = engine.update_state(metric, decision_iso)
                logger.info("AI 분석 완료")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[{self.subscription_id}] 분석 중 오류 발생: {e}")
                return
            _last_sample_ts = sample_ts

        targets = [
            a
            for a in _active_analyzers
            if a.is_running and a._delivered_state != state
        ]
        if not targets:
            return  # 모든 구독이 이미 이 상태를 받음 → 통지 안 보냄

        # await 전에 표시한다 — 전송 중 다른 분석기의 틱이 같은 상태를 중복 발송하지 않도록.
        for a in targets:
            a._delivered_state = state
        logger.info(
            f"AI 분석 결과: gNB2 {state} → 구독 {len(targets)}건 동시 전송 "
            f"({', '.join(f'{a.get_source_nf_type()}:{a.subscription_id[:8]}' for a in targets)})"
        )
        # 순차 await 이면 RICF 경로의 GUI 연출 대기(0.5s) 등이 PCF 전송을 밀어낸다.
        await asyncio.gather(
            *(a._deliver(state, decision_iso) for a in targets),
            return_exceptions=True,
        )

    async def _deliver(self, state: str, decision_iso: str) -> None:
        """gNB2 상태를 이 구독의 NF 형식(RICF 15f / PCF 14_e)으로 만들어 전송한다."""
        nf_type = self.get_source_nf_type()
        corr_id = self.subscription.notif_corr_id
        try:
            if nf_type == "RICF":
                cell_notif = build_15f_cell_power(
                    state, decision_iso, self.subscription_id, corr_id
                )
                self.control_data_store.add_data("ricf", corr_id, cell_notif[0])

                ncof_event_sub_notif = NncofEventsSubscriptionNotification.from_dict(cell_notif[0])
                cell_power_state = (ncof_event_sub_notif.event_notifications[0]  # type: ignore
                                    .cell_power_ctrl_opt_infos[0]
                                    .cell_power_ctrl_infos[0]
                                    .cell_power_param_sets[0]
                                    .cell_power_param_set.cell_power_state # type: ignore
                                    )
                logger.info(f"RICF 제어 데이터:")
                logger.info(f"CELL_POWER_STATE: {cell_power_state}")

                await self._notify_callback("ricf", cell_notif)

            elif nf_type == "PCF":
                qos_template = self._load_qos_template()
                if qos_template is None:
                    logger.warning("cannot retrieve qos template...")
                    return
                qos_notif = apply_qos_policy(
                    qos_template, state, decision_iso, self.subscription_id, corr_id
                )
                self.control_data_store.add_data("pcf", corr_id, qos_notif[0])

                ncof_event_sub_notif = NncofEventsSubscriptionNotification.from_dict(qos_notif[0])
                qos_param_sets = (ncof_event_sub_notif
                                 .event_notifications[0] # type: ignore
                                 .qos_pol_assist_infos[0]
                                 .qos_pol_assist_info[0]
                                 .qos_pol_assist_sets
                                #  .qos_param_set # type: ignore
                                )

                flow_desc = (ncof_event_sub_notif
                                 .event_notifications[0] # type: ignore
                                 .qos_pol_assist_infos[0].qos_pol_assist_info[0].qos_pol_assist_sets[0].f_descs # type: ignore
                )

                logger.info("PCF 제어 데이터:")
                if flow_desc is not None:
                    for flow in flow_desc:
                        logger.info(f"FLOW.IP_TRAFFIC_FILTER: {flow.ip_traffic_filter}")

                for set in qos_param_sets:
                    logger.info(f"GBR_DL: {set.qos_param_set.gbr_dl}")  #type: ignore
                # logger.info(f"qos_param_set: {qos_param_set.}") #type: ignore

                await self._notify_callback("pcf", qos_notif)

        except Exception as e:  # noqa: BLE001
            logger.warning(f"[{self.subscription_id}] 제어 명령 생성/전송 중 오류 발생: {e}")
