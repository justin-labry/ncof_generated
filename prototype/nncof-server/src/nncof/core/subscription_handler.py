# NF 구독 생애주기 관리 및 데이터 수신을 담당하는 SubscriptionHandler 클래스

import logging
import os
import asyncio
from typing import Any, List, Literal, Optional

import httpx
from fastapi.encoders import jsonable_encoder

from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nupf.models.notification_data import NotificationData

from .data_store import NotificationDataStore
from .nrf import nrf
from .subscription_request_builder import (
    build_subscription_requests,
    ExternalSubscriptionRequest,
)
from .data_analyzer import DataAnalyzer
from .websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)

_TLS_ENABLED = os.getenv("NCOF_TLS", "").strip().lower() in ("1", "true", "yes", "on")


def _httpx_kwargs() -> dict:
    """NCOF_TLS 설정 시 HTTP/2 over TLS(self-signed 허용), 기본은 h2c(평문 HTTP/2).
    평문에서 HTTP/2 를 쓰려면 http1=False 로 prior-knowledge h2c 를 강제해야 한다
    (http1=True 이면 평문 연결이 조용히 HTTP/1.1 로 떨어짐)."""
    return {"http2": True, "verify": False} if _TLS_ENABLED else {"http1": False, "http2": True}


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
    ):
        self.subscription_id = subscription_id
        self.subscription = subscription
        self._relation_manager = relation_manager
        self.notif_data_store = NotificationDataStore()
        self.control_data_store = NotificationDataStore()
        self.is_running = False
        self.external_subscriptions: List[ExternalSubscriptionRequest] = []
        self._client = httpx.AsyncClient(
            **_httpx_kwargs(), timeout=httpx.Timeout(5.0)
        )

        self._analyzer = DataAnalyzer(
            subscription_id=subscription_id,
            subscription=subscription,
            notif_data_store=self.notif_data_store,
            control_data_store=self.control_data_store,
            notify_callback=self._notify_subscriber,
        )

    def get_source_nf_type(self) -> Literal["PCF", "RICF"] | None:
        return self._analyzer.get_source_nf_type()

    async def _send_external_subscription(
        self, target: str, req_body: NsmfEventExposure | NefEventExposureSubsc
    ) -> Optional[str]:
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
                return external_sub_id
        except Exception as e:
            logger.warning(
                f"[{self.subscription_id}] {target.upper()} 연결 중 오류 발생: {e}"
            )
        return None

    async def _send_external_unsubscription(self, target: str, external_sub_id: str):
        """
        대상 NF 로 구독 해지 요청을 보낸다.
        """

        nf_uri = nrf.get_nf_uri(target)
        if not nf_uri:
            logger.warning(
                f"[{self.subscription_id}] NF URI 를 찾을 수 없음: {target}. 구독 해지 취소."
            )
            return

        unsubscription_url = f"{nf_uri}/subscriptions/{external_sub_id}"

        try:
            response = await self._client.delete(unsubscription_url)
            if response.status_code in (204, 200):
                return True
            else:
                logger.warning(
                    f"[{self.subscription_id}] {target.upper()} 구독 해지 실패 "
                    f"(Status: {response.status_code})."
                )
        except Exception as e:
            logger.error(
                f"[{self.subscription_id}] {target.upper()} 구독 해지 중 오류 발생: {e}"
            )

        try:
            await self._relation_manager.remove_relations_by_sub_id(external_sub_id)
        except Exception as e:
            logger.error(f"Failed to remove relation: {e}")

    async def _notify_subscriber(self, nf_type: str, ncof_control_event: list[dict]):
        """제어 명령을 NF(PCF 또는 RICF)로 전송한다."""
        if not self.subscription.notification_uri:
            logger.warning("notification_uri is missing")
            return

        try:
            response = await self._client.post(
                self.subscription.notification_uri, json=ncof_control_event
            )

            if response.status_code in (204, 200):
                logger.info(
                    f"[{self.subscription_id}] [{nf_type.upper()}]에게 제어명령 전송 완료"
                )

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

        except httpx.HTTPStatusError as e:
            logger.error(
                f"[{self.subscription_id}] HTTP 상태 오류\n"
                f"  status_code: {e.response.status_code}\n"
                f"  url: {e.request.url}\n"
                f"  response: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"[{self.subscription_id}] 제어명령 전송 중 오류 발생: {e}")

    async def start(self):
        """
        핸들러를 시작한다.
        1. 데이터 수집을 위한 외부 NF 구독 요청 전송
        2. 주기적 분석 태스크 시작 (DataAnalyzer 에 위임)
        """
        self.is_running = True
        logger.info(f"[{self.subscription_id}] 시작됨. 외부 NF 구독 절차 실행.")

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
        # if self._relation_manager is not None:
        await asyncio.sleep(1)
        for target, subscription, external_sub_id in successful:
            try:

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
            except Exception as e:
                logger.error(f"Failed to add relation: {e}")

        if self.subscription.evt_req and self.subscription.evt_req.rep_period:
            await self._analyzer.start()

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
        await self._client.aclose()
        logger.info(f"[{self.subscription_id}] 정지됨.")

    def handle_notification(
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
        logger.debug(
            f"[{self.subscription_id}] [{source_nf}] 데이터 수신, notif_id: [{notif_id}]"
        )

    def get_external_subscriptions(self) -> List[ExternalSubscriptionRequest]:
        return list(self.external_subscriptions)
