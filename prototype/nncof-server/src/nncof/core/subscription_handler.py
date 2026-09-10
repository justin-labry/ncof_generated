# NF 구독 생애주기 관리 및 데이터 수신을 담당하는 SubscriptionHandler 클래스

import asyncio
import logging
from rich.pretty import pretty_repr
import json

import os
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi.encoders import jsonable_encoder
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nupf.models.notification_data import NotificationData

from .data_analyzer import DataAnalyzer
from .data_store import NotificationDataStore
from .nrf import nrf
from .subscription_request_builder import (
    ExternalSubscriptionRequest,
    build_subscription_requests,
)
from .websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)

_TLS_ENABLED = os.getenv("NCOF_TLS", "").strip().lower() in ("1", "true", "yes", "on")


def _httpx_kwargs() -> dict:
    """NCOF_TLS 설정 시 HTTP/2 over TLS(self-signed 허용), 기본은 h2c(평문 HTTP/2).
    평문에서 HTTP/2 를 쓰려면 http1=False 로 prior-knowledge h2c 를 강제해야 한다
    (http1=True 이면 평문 연결이 조용히 HTTP/1.1 로 떨어짐)."""
    return (
        {"http2": True, "verify": False}
        if _TLS_ENABLED
        else {"http1": False, "http2": True}
    )


# TEMP(두두원 연동 우회) — 두두원이 notificationURI 를 고치면 딕셔너리를 비워 되돌린다.
# 두두원 sbi_poc_app 이 구독에 실어 보내는 notificationURI 는
#   PCF  http://10.254.73.46:55555/
#   RICF http://10.254.73.46:55556/
# 인데 실제 SBI 주소는 10.254.173.46 이다 — "173" 에서 "1" 이 빠진 한 글자 오타이며,
# 10.254.73.46 은 존재하지 않는 호스트라 ping 조차 응답하지 않는다.
# _notify_subscriber() 는 nrf 조회 없이 구독자가 준 URI 를 그대로 쓰기 때문에, 이 오타 하나로
# 제어 명령이 전부 `All connection attempts failed` 로 유실된다(구독·통지·분석·판정은 전부 정상).
# 두두원 회신을 기다리는 동안 종단 루프를 완주해 보기 위한 임시 치환이다.
_DODO1_NOTIF_URI_REWRITE: dict[str, str] = {"10.254.73.46": "10.254.173.46"}


def _rewrite_notif_uri(uri: str) -> str:
    """TEMP: 오타 IP 를 실제 주소로 바꾼 URL 을 돌려준다(대상이 아니면 원본 그대로).

    호스트 부분만 교체한다 — 경로·포트·스킴에 우연히 같은 문자열이 들어 있어도 건드리지 않는다.
    """
    if not _DODO1_NOTIF_URI_REWRITE:
        return uri
    parts = urlsplit(uri)
    right = _DODO1_NOTIF_URI_REWRITE.get(parts.hostname or "")
    if right is None:
        return uri
    netloc = right if parts.port is None else f"{right}:{parts.port}"
    return urlunsplit(parts._replace(netloc=netloc))


class SubscriptionHandler:
    """
    NF 구독 생애주기 관리 및 데이터 수신을 담당한다.
    - 외부 NF(SMF, UPF, RICF, AF)로 구독/구독해지 요청 전송
    - NF로부터 Notification 데이터 수신 및 DataStore 저장
    - 데이터 분석 및 제어 명령 생성은 DataAnalyzer 에 위임
    """

    def __init__(
        self,
        subscription_id: str,
        subscription: NncofEventsSubscription,
        max_data_entries: int = 100,
        relation_manager: Any = None,
        on_state_change: Callable[[], Awaitable[None]] | None = None,
        restored_notifications: list[dict] | None = None,
        restored_control_notifications: list[dict] | None = None,
        stale_external_subscriptions: list[dict] | None = None,
    ):
        self.subscription_id = subscription_id
        self.subscription = subscription
        self._relation_manager = relation_manager
        self._on_state_change = on_state_change
        self.notif_data_store = NotificationDataStore()
        self.control_data_store = NotificationDataStore()
        self.is_running = False
        self.external_subscriptions: list[ExternalSubscriptionRequest] = []
        self._stale_external_subscriptions = stale_external_subscriptions or []
        self._client = httpx.AsyncClient(**_httpx_kwargs(), timeout=httpx.Timeout(5.0))

        self._analyzer = DataAnalyzer(
            subscription_id=subscription_id,
            subscription=subscription,
            notif_data_store=self.notif_data_store,
            control_data_store=self.control_data_store,
            notify_callback=self._notify_subscriber,
        )
        self._restore_data_store(
            self.notif_data_store, restored_notifications or [], is_control=False
        )
        self._restore_data_store(
            self.control_data_store,
            restored_control_notifications or [],
            is_control=True,
        )

    def _restore_data_store(
        self, data_store: NotificationDataStore, entries: list[dict], is_control: bool
    ) -> None:
        """JSON 상태의 Notify 데이터를 분석기에 사용할 모델로 복원한다."""
        restored_entries = []
        for entry in entries:
            data = entry.get("data")
            source_nf = entry.get("source_nf", "unknown")
            if not is_control and isinstance(data, dict):
                if source_nf.lower() == "upf":
                    data = NotificationData.from_dict(data)
                else:
                    data = NefEventExposureNotif.from_dict(data)
            restored_entries.append({**entry, "data": data})
        data_store.restore_state(restored_entries)

    async def _state_changed(self) -> None:
        if self._on_state_change is not None:
            await self._on_state_change()

    def get_source_nf_type(self) -> Literal["PCF", "RICF"] | None:
        return self._analyzer.get_source_nf_type()

    async def _send_external_subscription(
        self, target: str, req_body: NsmfEventExposure | NefEventExposureSubsc
    ) -> str | None:
        """
        데이터 수집을 위한 대상 NF 로 구독 요청을 보낸다.
        """

        nf_uri = nrf.get_nf_uri(target)

        if not nf_uri:
            logger.warning(f"[{self.subscription_id}] NF URI 를 찾을 수 없음: {target}")
            return None

        subscription_url = f"{nf_uri}/subscriptions"

        try:
            response = await self._client.post(
                subscription_url, json=jsonable_encoder(req_body)
            )
            if response.status_code in (200, 201):
                resp_json = response.json()
                external_sub_id = resp_json.get("subscriptionId") or resp_json.get(
                    "subId"
                )
                if not external_sub_id and "Subscription-ID" in response.headers:
                    external_sub_id = response.headers["Subscription-ID"]
                if not external_sub_id:
                    logger.warning(
                        f"[{self.subscription_id}] {target.upper()} 로부터 ID 를 획득하지 못함 "
                        f"(Status: {response.status_code})."
                    )
                logger.info(f"[NCOF] --- [구독요청] ---> [{target.upper()}]")
                return external_sub_id
        except (httpx.RequestError, json.JSONDecodeError) as e:
            logger.warning(
                f"[{self.subscription_id}] {target.upper()} 연결 중 오류 발생: {e}"
            )
        return None

    async def _send_external_unsubscription(
        self, target: str, external_sub_id: str
    ) -> bool:
        """
        대상 NF 로 구독 해지 요청을 보낸다.
        """

        nf_uri = nrf.get_nf_uri(target)
        if not nf_uri:
            logger.warning(
                f"[{self.subscription_id}] NF URI 를 찾을 수 없음: {target}. 구독 해지 취소."
            )
            return False

        unsubscription_url = f"{nf_uri}/subscriptions/{external_sub_id}"

        try:
            response = await self._client.delete(unsubscription_url)
            if response.status_code in (204, 200, 404):
                if response.status_code == 404:
                    logger.info(
                        f"[{self.subscription_id}] {target.upper()} 하위 구독이 이미 없음"
                    )
                else:
                    logger.info(f"[NCOF] --- [구독해지요청] ---> [{target.upper()}]")
                if self._relation_manager is not None:
                    await self._relation_manager.remove_relations_by_sub_id(
                        external_sub_id
                    )
                return True
            else:
                logger.warning(
                    f"[{self.subscription_id}] {target.upper()} 구독 해지 실패 "
                    f"(Status: {response.status_code})."
                )
        except httpx.RequestError as e:
            logger.error(
                f"[{self.subscription_id}] {target.upper()} 구독 해지 중 오류 발생: {e}"
            )

        return False

    async def _notify_subscriber(self, nf_type: str, ncof_control_event: list[dict]):
        """제어 명령을 NF(PCF 또는 RICF)로 전송한다."""
        await self._state_changed()
        if not self.subscription.notification_uri:
            logger.warning("notification_uri is missing")
            return

        # TEMP: 발송 직전 URL 에만 치환을 적용한다. self.subscription.notification_uri 원본은
        # 그대로 두어야 구독 조회 응답과 상태 파일에 두두원이 보낸 값이 보존되고, 두두원이 오타를
        # 고치는 순간 별도 조치 없이 바른 주소가 쓰인다.
        notification_uri = _rewrite_notif_uri(self.subscription.notification_uri)
        if notification_uri != self.subscription.notification_uri:
            logger.warning(
                f"[{self.subscription_id}] TEMP 두두원 우회: 제어명령 대상 URI 치환 "
                f"{self.subscription.notification_uri} -> {notification_uri}"
            )

        try:
            response = await self._client.post(
                notification_uri, json=ncof_control_event
            )
        except httpx.RequestError as e:
            logger.error(f"[{self.subscription_id}] 제어명령 전송 중 오류 발생: {e}")
            return

        if response.status_code in (204, 200):
            logger.info(f"[NCOF] --- [제어명령] ---> [{nf_type.upper()}]")
            logger.info("\n%s", pretty_repr(ncof_control_event, expand_all=True))

            # if self._relation_manager is not None:
            #     await self._relation_manager.add_relation(
            #         from_node="ncof",
            #         to_node=nf_type.lower(),
            #         msg_type="NOTIFICATION",
            #         data=jsonable_encoder(ncof_control_event),
            #         sub_id=self.subscription_id,
            #     )

            _data = jsonable_encoder(ncof_control_event)
            if nf_type.lower() == "af" or nf_type.lower() == "ricf":
                await broadcast_web_message(
                    sub_id=self.subscription_id,
                    from_node="ncof",
                    to_node="nef",
                    msg_type="NOTIFICATION",
                    data=_data,
                )
                await asyncio.sleep(0.5)
                await broadcast_web_message(
                    sub_id=self.subscription_id,
                    from_node="nef",
                    to_node=nf_type.lower(),
                    msg_type="NOTIFICATION",
                    data=_data,
                )
            else:
                await broadcast_web_message(
                    sub_id=self.subscription_id,
                    from_node="ncof",
                    to_node=nf_type.lower(),
                    msg_type="NOTIFICATION",
                    data=_data,
                )
        else:
            logger.warning(
                f"[{self.subscription_id}] 제어명령 실패\n"
                f"  status_code: {response.status_code}\n"
                f"  url: {response.url}\n"
                f"  reason: {response.reason_phrase}\n"
                f"  response: {response.text}"
            )

    async def start(self):
        """
        핸들러를 시작한다.
        1. 데이터 수집을 위한 외부 NF 구독 요청 전송
        2. 주기적 분석 태스크 시작 (DataAnalyzer 에 위임)
        """
        self.is_running = True
        logger.info(
            f"[{self.subscription_id}] 구독 핸들러 시작. 외부 NF 구독 절차 실행."
        )

        for sub_info in self._stale_external_subscriptions:
            external_sub_id = sub_info.get("external_sub_id")
            if external_sub_id:
                await self._send_external_unsubscription(
                    sub_info["target"], external_sub_id
                )
        self._stale_external_subscriptions.clear()

        subscription_requests = build_subscription_requests(
            self.subscription_id, self.subscription
        )

        # Phase 1: 모든 외부 NF 구독 요청 전송
        successful: list[tuple[str, Any, str]] = []
        for sub_req in subscription_requests:
            target = sub_req.get("target")
            subscription = sub_req.get("subscription")

            external_sub_id = await self._send_external_subscription(
                target, subscription
            )

            if external_sub_id:
                successful.append((target, subscription, external_sub_id))
                self.external_subscriptions.append(
                    {
                        "target": target,
                        "external_sub_id": external_sub_id,
                        "subscription": subscription,
                    }
                )

        # Phase 2: 성공한 구독에 대해 relation 을 지연 시간을 두고 순차적으로 추가 (시각적 효과)
        if self._relation_manager is not None:
            await asyncio.sleep(1)
            for target, subscription, external_sub_id in successful:
                if target.lower() == "af" or target.lower() == "ricf":
                    await self._relation_manager.add_relation(
                        from_node="ncof",
                        to_node="nef",
                        msg_type="SUBSCRIBED",
                        data=jsonable_encoder(subscription),
                        sub_id=external_sub_id + "_nef",
                    )
                    await asyncio.sleep(0.5)
                    await self._relation_manager.add_relation(
                        from_node="nef",
                        to_node=target.lower(),
                        msg_type="SUBSCRIBED",
                        data=jsonable_encoder(subscription),
                        sub_id=external_sub_id,
                    )
                else:
                    await self._relation_manager.add_relation(
                        from_node="ncof",
                        to_node=target.lower(),
                        msg_type="SUBSCRIBED",
                        data=jsonable_encoder(subscription),
                        sub_id=external_sub_id,
                    )

                await asyncio.sleep(0.5)

        if self.subscription.evt_req and self.subscription.evt_req.rep_period:
            await self._analyzer.start()
        await self._state_changed()

    async def stop(self):
        """
        핸들러를 정지한다.
        1. 분석 태스크 중단 (DataAnalyzer 에 위임)
        2. 외부 NF 구독 해지
        3. HTTP 클라이언트 정리
        """
        self.is_running = False

        await self._analyzer.stop()

        logger.info(f"[{self.subscription_id}] 외부 NF 구독 해지 절차 시작")
        for sub_info in self.external_subscriptions:
            target = sub_info["target"]
            ext_id = sub_info["external_sub_id"]
            if ext_id:
                await self._send_external_unsubscription(target, ext_id)

        self.external_subscriptions.clear()
        self.notif_data_store.clear()
        self.control_data_store.clear()
        await self._client.aclose()
        logger.info(f"[{self.subscription_id}] 구독핸들러 정지됨.")

    async def shutdown(self):
        """서버 종료 시 하위 NF 구독은 유지하고 로컬 실행 자원만 정리한다."""
        self.is_running = False
        await self._analyzer.stop()
        await self._client.aclose()

    async def handle_notification(
        self, source_nf: str, notif_data: NotificationData | NefEventExposureNotif
    ):
        notif_id = None
        if isinstance(notif_data, NotificationData):
            notif_id = notif_data.correlation_id
        elif isinstance(notif_data, NefEventExposureNotif):
            notif_id = notif_data.notif_id

        if notif_id is None:
            logger.warning(
                "cannot retrieve notif_id - check correlation_id or notif_id field"
            )
            return

        self.notif_data_store.add_data(source_nf, notif_id, notif_data)
        await self._state_changed()
        logger.debug(
            f"[{self.subscription_id}] [{source_nf}] 데이터 수신, notif_id: [{notif_id}]"
        )

    def get_external_subscriptions(self) -> list[ExternalSubscriptionRequest]:
        return list(self.external_subscriptions)
