# 데이터 분석 및 제어 명령 생성을 담당하는 DataAnalyzer 클래스

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nupf.models.notification_data import NotificationData

from .data_store import NotificationDataStore
from .gnb2_rule_engine import Gnb2RuleEngine
from .websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)


def _now_iso_kst() -> str:
    """현재 시각을 ISO 8601 문자열로 반환한다. (로컬 타임존 기준)"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


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
        self.rule_engine = Gnb2RuleEngine()
        self._qos_template: list[dict] | None = None
        self._qos_template_path = Path(
            qos_template_path
            or Path(__file__).parent
            / "14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json"
        )

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
        self._task = asyncio.create_task(self._periodic_process())
        logger.info(f"[{self.subscription_id}] DataAnalyzer 시작됨")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.rule_engine = Gnb2RuleEngine()
        logger.info(f"[{self.subscription_id}] DataAnalyzer 중단됨")

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

                logger.info(f"[{self.subscription_id}] 주기적 분석 시작")

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

    def _get_wlan_performance_data(self) -> NotificationData | None:
        """
        UPF WLAN 성능 데이터를 notif_data_store 에서 조회한다.

        USER_DATA_USAGE_MEASURES 이벤트 타입의 NotificationData 를 반환하며,
        단순히 notification_items 개수만 확인하던 기존 로직을 개선하여
        실제 이벤트 타입으로 필터링한다.
        """
        notifications = self.notif_data_store.get_all()
        for notif in notifications.values():
            if not isinstance(notif, NotificationData):
                continue
            items = notif.notification_items
            if not items:
                continue
            for item in items:
                if item is not None and item.event_type == "USER_DATA_USAGE_MEASURES":
                    return notif
        return None

    async def _analyze_and_generate(self, nf_type: str) -> None:
        logger.info(f"[{self.subscription_id}] 데이터 분석 시작")

        qos_template = self._load_qos_template()
        if qos_template is None:
            logger.warning("cannot retrieve qos template...")
            return

        notif = self._get_wlan_performance_data()
        if notif is None:
            logger.warning("fail to retrieve wlan performance data...")
            return

        try:
            result = self.rule_engine.generate_notification(
                notif.to_dict(),
                qos_template,
                _now_iso_kst(),
                self.subscription_id,
                self.subscription.notif_corr_id,
            )
            if result is None:
                return

            cell_notif = result.get("cell_power_15f")
            qos_notif = result.get("qos_policy_14e")

            if cell_notif is not None and nf_type == "RICF":
                self.control_data_store.add_data(
                    "ricf", self.subscription.notif_corr_id, cell_notif[0]
                )
                await self._notify_callback("ricf", cell_notif)

            if qos_notif is not None and nf_type == "PCF":
                self.control_data_store.add_data(
                    "pcf", self.subscription.notif_corr_id, qos_notif[0]
                )
                await self._notify_callback("pcf", qos_notif)

        except Exception as e:
            logger.warning(f"[{self.subscription_id}] 분석 중 오류 발생: {e}")
