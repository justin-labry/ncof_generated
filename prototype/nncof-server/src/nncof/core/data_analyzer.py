# 데이터 분석 및 제어 명령 생성을 담당하는 DataAnalyzer 클래스

import asyncio
import itertools
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
from .decision_config import control_sequential, current_decision_config, wlan_sub_rep_period
from .gnb2_rl_engine import create_decision_engine
from .gnb2_rule_engine import Gnb2RuleEngine
from .websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)


# gNB2 판정은 프로세스 전체에서 하나여야 한다.
# 구독(PCF 의 QOS_POLICY_ASSIST, RICF 의 _CELL_POWER_CTRL)마다 분석기가 따로 돌며 각자 엔진 상태를 가지면,
# 한 판정의 두 절반인 15f(cellPowerState → RICF)와 14_e(NR gNB2 GBR → PCF)가 서로 다른 틱·서로 다른 UPF 샘플로
# 따로 결정된다(9/30 mock 실측: 지연 11~30초, 일치율 26% · 9/30 실망: PCF 에만 ACTIVE 14_e).
# 그래서 엔진을 하나 공유하고, **판정은 리더(가장 먼저 시작한 활성 구독)의 틱에서만** 한 번 한 뒤
# 그 상태를 아직 받지 못한 활성 구독 전부에 내보낸다(각 구독의 sub_id/corrId 로 스탬프). 보내는 순서는
# _control_order 를 따르고 앞 요청의 성공 응답을 받은 뒤 다음을 보낸다(GNB2_CONTROL_SEQUENTIAL=0 이면 예전처럼 동시).
# 다른 구독의 틱은 판정 없이 "아직 못 받은 상태" 만 전달한다 — 늦게 들어온 구독이 리더 틱을 기다리지 않게.
_shared_engine: Gnb2RuleEngine | None = None
_active_analyzers: list["DataAnalyzer"] = []
# shield 로 띄운 fan-out 은 참조가 사라지면 수거될 수 있어 끝날 때까지 들고 있는다.
_inflight_fanouts: set[asyncio.Future] = set()
# 순차 제어가 실패해 「처음부터 다시」 를 기다리는 중 — 재시도는 리더 판정 틱에서만(10/26 회신 「다음 판정 주기」).
# 다른 구독의 틱이 실패 1초 안에 같은 요청을 되풀이하지 않게 한다.
_retry_on_leader_tick = False
# 저장 구독 복원 중에는 내보내지 않는다 — 복원은 상태파일 순서로 한 건씩 돌아, 앞 구독(PCF, 리더)의 틱이 아직 복원되지
# 않은 구독(RICF)을 빼고 내보내면 켤 때 15f 없이 14_e 만 나간다(E2E: RICF 복원 12초 동안 ACTIVE 14_e 단독).
_restoring = False


def set_restoring(flag: bool) -> None:
    """SubscriptionManager 가 저장 구독을 복원하는 동안 제어 전송을 멈춘다 — 끝나면 다음 틱에 순서대로 보낸다."""
    global _restoring
    _restoring = flag
# trend 판정의 비교 기준 — 12p_c 스트림(notifId)별로 지난 판정 때 본 (timeStamp, Mbps). 공유 엔진과 수명을 같이한다.
# "바로 앞 10초 샘플" 이 아니라 "지난 판정 때 값" 과 비교해야 판정 틱(상향 repPeriod) 사이에 쌓인 변화가 빠지지 않는다.
_trend_refs: dict[str, tuple[datetime, float]] = {}

# 판정 입력으로 쓰는 하위 구독 이벤트 — 12p_c(WLAN) 스트림. SubscriptionHandler 가 그 SMF 하위 구독의 notifId 를 알려 준다.
WLAN_SOURCE_EVENT = "WLAN_PERFORMANCE"


def _get_shared_engine() -> Gnb2RuleEngine:
    global _shared_engine
    if _shared_engine is None:
        # NCOF_DECISION_ENGINE(rule|rl) 환경변수에 따라 룰 베이스 또는 RL 정책
        # 엔진을 생성한다 (RL 로드 실패 시 룰로 폴백). 판정 설정은 ncof_setting.conf 의 GNB2_*.
        _shared_engine = create_decision_engine()
        _shared_engine.apply_config(current_decision_config())
    return _shared_engine


def _leader() -> "DataAnalyzer | None":
    """판정을 맡는 분석기 — 시작 순서상 첫 활성 분석기(PCF/RICF 구독). 빠지면 다음 것이 이어받는다."""
    for a in _active_analyzers:
        if a.is_running and a.get_source_nf_type() is not None:
            return a
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# 순차 제어 한 단계(상태 저장 + POST)의 상한 — httpx 5초 타임아웃이 못 막는 대기(상태 저장 잠금 등)에서
# 진행 중 fan-out 이 영영 끝나지 않아 모든 제어가 멈추는 것을 막는다.
_STEP_TIMEOUT_SEC = 20.0


def _control_order(state: str) -> tuple[str, ...]:
    """두두원과 정한 제어 순서(10/26 회신) — gNB2 를 켤 때는 셀부터(15f ACTIVE → 14_e 분산 비율),
    끌 때는 트래픽부터(14_e 0:100 → 15f DEEP_SLEEP). 직전 상태가 아니라 목표 상태로 정하므로
    재기동 직후나 실패 뒤 다시 보낼 때도 같은 규칙이다."""
    return ("RICF", "PCF") if state == "ACTIVE" else ("PCF", "RICF")


def _held_by_peer(
    nf: str,
    targets: list["DataAnalyzer"],
    state: str,
    split: tuple[int, int] | None,
    gnb1_split: tuple[int, int] | None,
) -> bool:
    """이번 묶음 밖의 같은 NF 활성 구독 중 이 상태(PCF 는 split 까지)를 이미 받은 것이 있는가."""
    return any(
        b.is_running
        and b not in targets
        and b.get_source_nf_type() == nf
        and not b._needs_delivery(state, split, gnb1_split)
        for b in _active_analyzers
    )


def _clear_delivery_records() -> list["DataAnalyzer"]:
    """활성 분석기 전부의 전달 기록을 지운다 — 다음 틱에 목표 상태 순서의 처음부터 모두 다시 보낸다.
    같은 상태를 두 번 받아도 무해(UPF 같은 비율 · network_status UPDATE). 기록이 있던 분석기를 돌려준다."""
    cleared = [a for a in _active_analyzers if a._delivered_state is not None]
    for a in cleared:
        a._delivered_state = None
        a._delivered_split = None
        a._delivered_gnb1_split = None
    return cleared


async def _deliver_in_order(
    targets: list["DataAnalyzer"],
    state: str,
    split: tuple[int, int] | None,
    gnb1_split: tuple[int, int] | None,
    decision_iso: str,
) -> None:
    """targets(이미 _control_order 로 정렬)를 NF 단계별로 보내고, 앞 단계가 성공 응답(200)을 받아야 다음 단계를 보낸다.
    한 단계에서 하나도 성공하지 못하면 뒤 단계는 보내지 않고 활성 구독 전부(묶음 밖 포함)의 전달 기록을 지운다 —
    다음 판정 틱(리더 틱)에 처음부터 다시 보낸다(10/26 회신 「앞 요청이 실패하면 … 다음 판정 주기에 처음부터 다시」).
    같은 NF 구독이 둘 이상(고아 상향 트리)이면 그중 하나라도 성공하면 단계를 통과하고, 실패한 구독만
    (_deliver 가 이미 되돌림) 다음 틱에 그 구독만 다시 받는다 — 죽은 구독 하나가 전체 제어를 막지 않게."""
    global _retry_on_leader_tick
    order = _control_order(state)

    def nf_of(a: "DataAnalyzer") -> str:
        nf = a.get_source_nf_type()
        return nf if nf in order else "?"

    def forget_all() -> None:
        for b in targets:
            b._forget_delivery(state, split, gnb1_split)

    phases = [list(g) for _, g in itertools.groupby(targets, key=nf_of)]
    names = [nf_of(g[0]) for g in phases]
    for p, group in enumerate(phases):
        if len(group) > 1:
            logger.warning(
                f"순차 제어: {names[p]} 구독 {len(group)}건({', '.join(a.subscription_id[:8] for a in group)}) "
                f"— 같은 장비에 겹친 상향 구독(고아 트리)인지 확인"
            )
        attempted = succeeded = 0
        for a in group:
            if not a.is_running:  # 시퀀스 도중 구독 삭제 · 감시 만료 · 서버 종료 — 보내지 않는다
                logger.info(f"순차 제어: {names[p]}:{a.subscription_id[:8]} 는 그새 멈춤 — 건너뜀")
                continue
            attempted += 1
            try:
                ok = await asyncio.wait_for(
                    a._deliver(state, split, gnb1_split, decision_iso), _STEP_TIMEOUT_SEC
                )
            except TimeoutError:  # _deliver 는 취소되며 자기 표시를 되돌렸다
                logger.warning(
                    f"순차 제어: {names[p]}:{a.subscription_id[:8]} {_STEP_TIMEOUT_SEC:.0f}초 안에 끝나지 않음 — 실패로 본다"
                )
                ok = False
            except asyncio.CancelledError:
                forget_all()
                raise
            succeeded += bool(ok)
        step = f"{p + 1}/{len(phases)} {names[p]}"
        if not succeeded and attempted and _held_by_peer(names[p], targets, state, split, gnb1_split):
            # 이 단계에 남은 것은 같은 NF 의 겹친 구독뿐이고 다른 구독이 이미 이 상태를 받았다(장비에는 가 있다) —
            # 고아 하나가 단계만 바뀌는 14_e 를 영영 막지 않게 넘어간다(실패한 구독은 _deliver 가 되돌려 다음 틱에 다시).
            after = f" → {names[p + 1]}" if p + 1 < len(phases) else " — 완료"
            logger.warning(f"순차 제어 {step} 겹친 구독만 실패 — 다른 {names[p]} 구독이 이미 {state} 를 받음{after}")
            continue
        # 하나도 성공 못 함 — 보냈다가 실패했거나, 다 멈춰서 하나도 못 보냈는데 뒤 단계가 남았을 때(확인 없이 다음을 보내지 않는다)
        if not succeeded and (attempted or p + 1 < len(phases)):
            rest = names[p + 1:]
            skipped = f"{'·'.join(rest)} 는 보내지 않음, " if rest else ""
            logger.warning(f"순차 제어 {step} 실패 — {skipped}다음 판정 틱에 처음부터 다시 보냄")
            # 이번 묶음만이 아니라 전부 지운다 — 하나도 성공 못 함은 두두원 앱이 내려갔다 다시 뜬 것일 수 있고(새 앱은 gNB2 OFF),
            # 묶음 밖 구독의 기록도 옛 앱에 보낸 것이다. 그대로 두면 단계만 바뀐 14_e 재시도가 새 PCF 구독이 붙기 전(약 4초)
            # 옛 PCF 구독으로 15f 없이 새 앱에 닿는다. 다시 보낼 때는 목표 상태 순서의 처음(ON 이면 15f ACTIVE)부터.
            _clear_delivery_records()
            _retry_on_leader_tick = True
            return
        after = f" → {names[p + 1]}" if p + 1 < len(phases) else " — 완료"
        if attempted:
            logger.info(f"순차 제어 {step} 성공 응답 확인{after}")
        else:  # 마지막 단계 대상이 전부 그새 멈춤 — 보낸 것이 없으니 「성공 응답」 이라 쓰지 않는다
            logger.info(f"순차 제어 {step} 대상이 모두 멈춰 보내지 않음{after}")
    # 겹친 구독 중 실패해 되돌린 것이 남았으면(위 _held_by_peer 통과 · 단계 안 일부 실패) 그 재시도도 리더 판정 틱에서만 —
    # 다른 구독 틱마다 고아에 다시 보내면 판정 주기당 구독 수만큼 시도하고, 타임아웃 고아는 전송 슬롯을 거의 늘 차지한다.
    _retry_on_leader_tick = any(
        b.is_running and b._needs_delivery(state, split, gnb1_split) for b in targets
    )


# 판정 입력 샘플의 허용 나이 = repPeriod × 이 값. 두두원은 무트래픽이면 12p_c 를 아예 보내지 않고(9/28 `udptp metric
# incomplete`), 보고 주기도 약 61초씩 밀린다. 끊긴 스트림의 마지막 값으로 계속 판정하면 상태가 그 값에 고정되고,
# 그 사이 임계를 바꾸면 몇 시간 전 값으로 실장비 제어가 나간다(10/1 실측: 12p_c 가 02:58:40 이후 끊김).
_STALE_FACTOR = 3


def _splits_text(split: tuple[int, int] | None, gnb1_split: tuple[int, int] | None) -> str:
    """로그용 'gNB2:WLAN 700:300 Mbps · gNB1:WLAN 700:300 Mbps'."""
    text = f"gNB2:WLAN {split[0]}:{split[1]} Mbps" if split else ""
    if gnb1_split:
        text += f" · gNB1:WLAN {gnb1_split[0]}:{gnb1_split[1]} Mbps"
    return text


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
        self._delivered_state: str | None = None
        # level 모드에서 마지막으로 내보낸 (NR gNB2, WLAN) · (NR gNB1, WLAN) split — PCF 는 상태가 같아도 바뀌면 다시 보낸다
        self._delivered_split: tuple[int, int] | None = None
        self._delivered_gnb1_split: tuple[int, int] | None = None
        # 이 구독의 WLAN_PERFORMANCE SMF 하위 구독 notifId(= 12p_c 통지의 correlationId)
        self._wlan_stream_ids: set[str] = set()
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

    def set_wlan_stream_ids(self, notif_ids: set[str]) -> None:
        """판정 입력으로 쓸 WLAN(12p_c) 스트림의 notifId 들을 받는다 — SubscriptionHandler.start() 가 호출."""
        self._wlan_stream_ids = set(notif_ids)

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
        self._join_active_analyzers()
        self._task = asyncio.create_task(self._periodic_process())

    def _join_active_analyzers(self) -> None:
        """fan-out 대상에 든다. 순차 모드에서 다른 구독이 이미 있으면 그 구독들의 전달 기록을 지운다 —
        운영 중 새 상향 구독 = 두두원 앱 재기동(새 앱은 gNB2 를 OFF 로 초기화)이나 재구독인데, 남은 기록은 옛 앱에 보낸 것이다.
        그대로 두면 옛 RICF 는 「이미 받음」 이라 새 PCF 에만 14_e 가 나가 15f ACTIVE 보다 앞선다(새 RICF 는 4 ~ 6초 뒤에 온다).
        지우면 다음 틱에 15f(옛 RICF 구독도 같은 :55556 의 새 앱에 닿는다) → 200 → 14_e 순서로 다시 보내고,
        그 15f 가 실패하면 14_e 는 보내지 않는다."""
        if self in _active_analyzers:
            return
        if control_sequential():
            stale = _clear_delivery_records()
            if stale:  # 앞 실패로 이미 지워졌으면 지울 것이 없어 찍지 않는다
                logger.info(
                    f"[{self.subscription_id}] 새 상향 구독 — 남은 구독 {len(stale)}건"
                    f"({', '.join(f'{a.get_source_nf_type()}:{a.subscription_id[:8]}' for a in stale)})의 전달 기록을 지움, "
                    f"다음 틱에 순서대로 다시 보냄"
                )
        _active_analyzers.append(self)

    async def stop(self):
        self.is_running = False
        self._leave_active_analyzers()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001 — 구독 해지·상태 저장이 끝까지 가도록
                logger.warning(f"[{self.subscription_id}] 분석 태스크가 오류로 끝나 있었음: {e}")
        logger.info(f"[{self.subscription_id}] DataAnalyzer 중단됨")

    def _leave_active_analyzers(self) -> None:
        """fan-out 대상에서 빠진다. 마지막 분석기가 빠지면 공유 엔진을 버려,
        다음 구독이 첫 판정부터 새 엔진으로 시작하게 한다 (예전의 분석기별 엔진 재생성과 같은 효과)."""
        global _shared_engine, _retry_on_leader_tick
        self._delivered_state = None
        self._delivered_split = None
        self._delivered_gnb1_split = None
        if self in _active_analyzers:
            _active_analyzers.remove(self)
            if not _active_analyzers:
                _shared_engine = None
                _retry_on_leader_tick = False
                _trend_refs.clear()

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

        # 판정 틱은 상향 repPeriod 를 따른다 — 두두원이 다시 구독하면(청소 후 재기동 등) 60 으로 돌아온다
        wlan_period = wlan_sub_rep_period()
        if wlan_period and (period > 2 * wlan_period or wlan_period > _STALE_FACTOR * period):
            logger.warning(
                f"[{self.subscription_id}] 판정 틱 {period}초(상향 repPeriod)와 WLAN 하위 {wlan_period}초가 맞지 않음 — "
                f"틱이 2배 넘게 길면 추세 반응이 늦고, WLAN 이 틱×{_STALE_FACTOR} 를 넘으면 매 틱 판정 보류"
            )

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

                try:
                    await self._analyze_and_generate(nf_type)
                except Exception:  # noqa: BLE001 — 한 틱의 오류로 판정 루프(와 fan-out 대상 등록)가 끝나면 안 된다
                    logger.exception(f"[{self.subscription_id}] 분석 틱 오류 — 다음 틱에 계속")


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

    def _wlan_samples(self) -> list[tuple[str, NotificationData, datetime]]:
        """판정 입력 후보 (notifId, 통지, timeStamp) 전부 — 활성 구독 전부의 store 에서.

        - 판정은 프로세스 공유이므로 활성 구독 전부의 store 에서 고른다.
        - **WLAN_PERFORMANCE 하위 구독(12p_c) 스트림만** 쓴다. 한 구독의 두 UPF 스트림(8_ SERVICE_EXPERIENCE 와
          12p_c WLAN) 중 "가장 늦게 온 것" 을 고르던 예전 방식은 도착 순서에 따라 의미가 다른 합계(9/30 실망 8_ ≈104 Mbps
          vs 12p_c ≈285 Mbps)를 번갈아 써서, 8_ 이상값(12458.99595 Mbps)으로 ACTIVE 오판을 냈다.
        - WLAN 스트림이 설정된 구독이 하나도 없을 때만 예전처럼 아무 UDUM 이나 쓴다(하위 호환).
        """
        pool = list(_active_analyzers)
        if self not in pool:
            pool.append(self)
        wlan_only = any(a._wlan_stream_ids for a in pool)

        samples: list[tuple[str, NotificationData, datetime]] = []
        for a in pool:
            for notif_id, notif in a.notif_data_store.get_all().items():
                if wlan_only and notif_id not in a._wlan_stream_ids:
                    continue
                ts = self._udum_timestamp(notif)
                if ts is None:
                    continue
                samples.append((notif_id, notif, ts))
        return samples

    def _get_wlan_performance_data(self) -> tuple[NotificationData, datetime, str] | None:
        """
        판정 입력(UPF USER_DATA_USAGE_MEASURES)과 그 timeStamp·notifId 를 조회한다(후보는 _wlan_samples).

        timeStamp 가 가장 최신인 것을 반환한다. 저장 순서상 첫 번째 것을 고르면, 그 스트림의
        주기 통지가 끊겼을 때 갱신되지 않는 값을 계속 읽어 분석 결과가 고정된다.
        """
        newest: tuple[str, NotificationData, datetime] | None = None
        for sample in self._wlan_samples():
            if newest is None or sample[2] > newest[2]:
                newest = sample
        if newest is None:
            return None
        notif_id, notif, ts = newest
        return notif, ts, notif_id

    @staticmethod
    def _trend_reference(notif_id: str, sample_ts: datetime, max_gap_sec: float) -> tuple[float, datetime] | None:
        """같은 스트림을 지난 판정 때 본 (값, timeStamp). 없거나 max_gap_sec 넘게 떨어져 있으면(끊긴 뒤) None.
        지난 판정 뒤 새 샘플이 없으면 같은 샘플이 돌아온다(Δ 0 → 상태 유지)."""
        ref = _trend_refs.get(notif_id)
        if ref is None:
            return None
        ref_ts, ref_value = ref
        if ref_ts > sample_ts or (sample_ts - ref_ts).total_seconds() > max_gap_sec:
            return None
        return ref_value, ref_ts

    def _snapshot_trend_refs(self) -> None:
        """판정한 틱마다 모든 12p_c 스트림의 최신 (timeStamp, 값)을 다음 판정의 비교 기준으로 남긴다.
        PCF·RICF 트리 중 어느 스트림이 다음 틱의 최신이 되어도 자기 스트림의 지난 판정 값과 비교하게 한다."""
        refs = {
            notif_id: (ts, extract_wlan_dl_mbps(notif.to_dict()))
            for notif_id, notif, ts in self._wlan_samples()
        }
        _trend_refs.clear()
        _trend_refs.update(refs)

    async def _analyze_and_generate(self, nf_type: str) -> None:
        """리더 틱이면 판정해 공유 엔진에 반영하고, 그 상태를 아직 받지 못한 활성 구독 전부
        (RICF 15f · PCF 14_e)에 _control_order 순서로 내보낸다. 리더가 아니면 판정 없이 전달만 한다."""
        engine = self.decision_engine
        decision_iso = _now_iso_kst()
        leader = _leader()

        if leader is self:
            sample = self._get_wlan_performance_data()
            rep_period = (self.subscription.evt_req.rep_period if self.subscription.evt_req else None) or 60
            age = (_utcnow() - sample[1]).total_seconds() if sample else None
            if sample is None:
                logger.warning(
                    "fail to retrieve wlan performance data... (판정 입력 12p_c 샘플 없음 — 판정 보류)"
                )
            elif age > _STALE_FACTOR * rep_period:
                logger.warning(
                    f"판정 입력 12p_c 끊김: 마지막 샘플 {sample[1].astimezone().isoformat(timespec='seconds')}"
                    f"({age:.0f}초 전, 허용 {_STALE_FACTOR * rep_period}초) — 판정 보류"
                )
            else:
                wlan_perf_data, sample_ts, stream_id = sample
                logger.info(f"RLlib 입력 데이터 추출:")
                try:
                    config = current_decision_config()
                    engine.apply_config(config)
                    metric = extract_wlan_dl_mbps(wlan_perf_data.to_dict())
                    prev = self._trend_reference(stream_id, sample_ts, _STALE_FACTOR * rep_period)
                    logger.info(
                        f"입력 샘플 timeStamp {sample_ts.astimezone().isoformat(timespec='seconds')}({age:.0f}초 전)"
                    )
                    logger.info(f"분석 메트릭 WLAN_DL_MBPS:{metric}")
                    if config.mode == "trend":
                        if engine.last_emitted_state is None:
                            logger.info(f"추세 입력: 첫 판정 — TH {config.th_mbps} 기준 판정")
                        elif prev is None:
                            logger.info(f"추세 입력: 지난 판정 값 없음(끊긴 뒤) — TH {config.th_mbps} 기준 판정")
                        else:
                            logger.info(
                                f"추세 입력: 지난 판정 {prev[0]} → 현재 {metric} Mbps (Δ {metric - prev[0]:+.1f}, "
                                f"지난 판정 샘플 {prev[1].astimezone().isoformat(timespec='seconds')}, "
                                f"TH {config.th_mbps} · DEADBAND {config.trend_deadband_mbps})"
                            )
                    logger.info("AI 분석 시작")
                    engine.update_state(metric, decision_iso, prev[0] if prev else None)
                    if engine.last_emitted_split is not None:
                        bounds = "/".join(f"{b:g}" for b in config.level_bounds_mbps)
                        logger.info(
                            f"단계 판정: WLAN {metric} Mbps → 단계 {engine.last_emitted_level} "
                            f"{engine.last_emitted_state} ({_splits_text(engine.last_emitted_split, engine.last_emitted_gnb1_split)}"
                            f", 경계 {bounds})"
                        )
                    self._snapshot_trend_refs()
                    logger.info("AI 분석 완료")
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[{self.subscription_id}] 분석 중 오류 발생: {e}")
                    return
        elif leader is not None:
            logger.debug(
                f"[{self.subscription_id}] 판정은 리더 구독 {leader.subscription_id[:8]} 의 틱에서 한다 — 이번 틱은 전달만"
            )

        state = engine.last_emitted_state
        if state is None:
            return  # 아직 첫 판정 전
        await self._fan_out(state, engine.last_emitted_split, engine.last_emitted_gnb1_split, decision_iso)

    def _needs_delivery(
        self, state: str, split: tuple[int, int] | None, gnb1_split: tuple[int, int] | None
    ) -> bool:
        """RICF(15f 셀 상태)는 상태가 바뀔 때만, PCF(14_e gbr/mbr)는 level 모드 split 만 바뀌어도 보낸다."""
        if self._delivered_state != state:
            return True
        return self.get_source_nf_type() == "PCF" and (
            self._delivered_split != split or self._delivered_gnb1_split != gnb1_split
        )

    async def _fan_out(
        self,
        state: str,
        split: tuple[int, int] | None,
        gnb1_split: tuple[int, int] | None,
        decision_iso: str,
    ) -> None:
        global _retry_on_leader_tick
        if _restoring:
            return  # 저장 구독 복원 중 — 끝난 뒤 틱에서 순서대로
        if any(not f.done() for f in _inflight_fanouts):
            # 앞 전송이 아직 응답을 기다린다 — 그 사이 다른 분석기의 틱이 끼어들면 순서가 섞인다. 끝난 뒤 틱에서 이어 간다.
            logger.debug(f"[{self.subscription_id}] 앞 제어 전송이 아직 끝나지 않음 — 이번 틱은 건너뜀")
            return
        if _retry_on_leader_tick and _leader() is not self and control_sequential():
            return  # 실패한 묶음은 리더 판정 틱에서 처음부터 — 다른 구독의 틱이 곧바로 되풀이하지 않게
        targets = [
            a
            for a in _active_analyzers
            if a.is_running and a._needs_delivery(state, split, gnb1_split)
        ]
        if not targets:
            return  # 모든 구독이 이미 이 상태(와 split)를 받음 → 통지 안 보냄

        sequential = control_sequential()
        if not sequential:
            _retry_on_leader_tick = False  # 동시 모드 — 예전처럼 어느 틱이든 실패한 대상만 다시
        if sequential:
            order = _control_order(state)
            targets.sort(
                key=lambda a: order.index(a.get_source_nf_type())
                if a.get_source_nf_type() in order
                else len(order)
            )
            if state == "ACTIVE" and not any(
                a.is_running and a.get_source_nf_type() == "RICF" for a in _active_analyzers
            ):
                logger.warning("순차 제어: RICF 구독이 없어 15f ACTIVE 확인 없이 14_e 만 보낸다")
        # await 전에 표시한다 — 전송 중 다른 분석기의 틱이 같은 상태를 중복 발송하지 않도록.
        for a in targets:
            a._delivered_state = state
            a._delivered_split = split
            a._delivered_gnb1_split = gnb1_split
        split_text = f" · {_splits_text(split, gnb1_split)}" if split else ""
        logger.info(
            f"AI 분석 결과: gNB2 {state}{split_text} → 구독 {len(targets)}건 {'순차' if sequential else '동시'} 전송 "
            f"({', '.join(f'{a.get_source_nf_type()}:{a.subscription_id[:8]}' for a in targets)})"
        )
        # shield: 이 틱을 돈 분석기가 전송 도중 stop() 되어도 다른 구독으로 가는 전송은 끝까지 간다.
        if sequential:
            fanout = asyncio.ensure_future(
                _deliver_in_order(targets, state, split, gnb1_split, decision_iso)
            )
        else:
            fanout = asyncio.gather(
                *(a._deliver(state, split, gnb1_split, decision_iso) for a in targets),
                return_exceptions=True,
            )
        _inflight_fanouts.add(fanout)
        fanout.add_done_callback(_inflight_fanouts.discard)
        await asyncio.shield(fanout)

    def _forget_delivery(
        self, state: str, split: tuple[int, int] | None, gnb1_split: tuple[int, int] | None
    ) -> None:
        """전송이 끝나지 못했으면 표시를 되돌려 다음 틱(리더든 자기 틱이든)에 다시 보내게 한다."""
        if (
            self.is_running
            and self._delivered_state == state
            and self._delivered_split == split
            and self._delivered_gnb1_split == gnb1_split
        ):
            self._delivered_state = None
            self._delivered_split = None
            self._delivered_gnb1_split = None

    async def _deliver(
        self,
        state: str,
        split: tuple[int, int] | None,
        gnb1_split: tuple[int, int] | None,
        decision_iso: str,
    ) -> bool:
        """gNB2 상태를 이 구독의 NF 형식(RICF 15f / PCF 14_e)으로 만들어 전송한다. 상대가 성공 응답을 주면 True."""
        nf_type = self.get_source_nf_type()
        corr_id = self.subscription.notif_corr_id
        delivered = True
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

                delivered = await self._notify_callback("ricf", cell_notif) is not False

            elif nf_type == "PCF":
                qos_template = self._load_qos_template()
                if qos_template is None:
                    logger.warning("cannot retrieve qos template...")
                    self._forget_delivery(state, split, gnb1_split)
                    return False
                qos_notif = apply_qos_policy(
                    qos_template, state, decision_iso, self.subscription_id, corr_id, split, gnb1_split
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

                delivered = await self._notify_callback("pcf", qos_notif) is not False

        except asyncio.CancelledError:
            self._forget_delivery(state, split, gnb1_split)
            raise
        except Exception as e:  # noqa: BLE001
            delivered = False
            logger.warning(f"[{self.subscription_id}] 제어 명령 생성/전송 중 오류 발생: {e}")

        if not delivered:
            self._forget_delivery(state, split, gnb1_split)
        return delivered
