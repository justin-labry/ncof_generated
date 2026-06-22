import uuid
import logging
import json
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder

from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc

from nncof.models.nncof_events_subscription import NncofEventsSubscription

from .websocket_manager import broadcast_web_message
from .subscription_handler import SubscriptionHandler

logger = logging.getLogger(__name__)


def _normalize_subscription(
    subscription: Any,
    subscription_id: str | None,
) -> Dict[str, Any]:
    """
    NncofEventsSubscription / NsmfEventExposure / NefEventExposureSubsc 세 타입의
    구독 객체를 공통 구조의 dict로 변환한다.

    Args:
        subscription: 변환할 구독 객체.
        subscription_id: SubscriptionManager 의 키로 사용되는 구독 ID.

    Returns:
        {
            "subscriptionId": str,
            "notifUri": str,
            "eventReq": {
                "notificationMethod": str (기본값 "PERIODIC"),
                "repPeriod": int (기본값 60),
            },
            "eventSubscriptions": [{ "event": str }, ...]
        }
    """
    sub_id = subscription_id if subscription_id else ""
    if isinstance(subscription, NsmfEventExposure):
        sub_id = subscription.sub_id or subscription_id

    notif_uri = ""
    if isinstance(subscription, NncofEventsSubscription):
        notif_uri = subscription.notification_uri or ""
    elif isinstance(subscription, NsmfEventExposure):
        notif_uri = subscription.notif_uri or ""
    elif isinstance(subscription, NefEventExposureSubsc):
        notif_uri = subscription.notif_uri or ""

    notif_method = "PERIODIC"
    rep_period = 60
    from_node = ""
    if isinstance(subscription, NncofEventsSubscription):
        if subscription.evt_req is not None:
            notif_method = subscription.evt_req.notif_method or notif_method
            rep_period = subscription.evt_req.rep_period or rep_period
            nf_id = (
                subscription.cons_nf_info.nf_id
                if subscription.cons_nf_info and subscription.cons_nf_info.nf_id
                else ""
            )

            # nf_id = subscription_request.cons_nf_info.nf_id
            if nf_id.startswith("pcf"):
                from_node = "pcf"
            elif nf_id.startswith("ricf"):
                from_node = "ricf"
            else:
                from_node = "unknown"

    elif isinstance(subscription, NsmfEventExposure):
        notif_method = subscription.notif_method or notif_method
        rep_period = subscription.rep_period or rep_period
    elif isinstance(subscription, NefEventExposureSubsc):
        if subscription.events_rep_info is not None:
            notif_method = subscription.events_rep_info.notif_method or notif_method
            rep_period = subscription.events_rep_info.rep_period or rep_period

    event_subs: List[Dict[str, str]] = []

    if isinstance(subscription, NncofEventsSubscription):
        if subscription.event_subscriptions:
            for es in subscription.event_subscriptions:
                event_subs.append({"event": es.event})
    elif isinstance(subscription, NsmfEventExposure):
        if subscription.event_subs:
            for es in subscription.event_subs:
                event_subs.append({"event": es.event})
    elif isinstance(subscription, NefEventExposureSubsc):
        if subscription.events_subs:
            for es in subscription.events_subs:
                event_subs.append({"event": es.event})

    return {
        "subscriptionId": sub_id,
        "notifUri": notif_uri,
        "fromNode": from_node,
        "eventReq": {
            "notificationMethod": notif_method,
            "repPeriod": rep_period,
        },
        # "eventSubscriptions": event_subs,
        "data": subscription,
    }


def getSubscriptionManager():
    return SubscriptionManager()


class SubscriptionManager:
    """
    SubscriptionManager 는 구독 핸들러를 관리하는 기능을 제공한다.
    새로운 구독요청이 발생하면 SubscriptionHandler 객체를 생성하고 관리한다.

    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SubscriptionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, nf_service_discovery=None):
        if self._initialized:
            return
        self.nf_service_discovery = nf_service_discovery
        self.subscriptions: Dict[str, SubscriptionHandler] = {}
        self.active_relations = []  # [{from, to, type, data, sub_id}]
        self._initialized = True
        logger.info("[SubscriptionManager] 싱글톤 인스턴스가 초기화.")

    def _get_from_node(self, nf_id: str) -> str | None:

        PCF = "pcf"
        RICF = "ricf"

        from_node = None
        if nf_id.startswith(PCF):
            from_node = PCF
        elif nf_id.startswith(RICF):
            from_node = RICF
        else:
            from_node = "Unknown"
        return from_node

    def get_nf_id(self, sub_req: NncofEventsSubscription):
        nf_info = sub_req.cons_nf_info
        nf_id = getattr(nf_info, "nf_id")
        return nf_id

    async def create_subscription(
        self, subscription_request: NncofEventsSubscription
    ) -> str:
        """
        새로운 구독 요청을 휘한 핸들러를 생성하고 관리한다.

        Args:
            subscription_request (NncofEventsSubscription): 구독 요청 모델 객체

        Returns:
            str: 생성된 구독 ID
        """

        nf_id = self.get_nf_id(subscription_request)

        from_node = self._get_from_node(nf_id)

        # 1. 구독 ID 생성
        subscription_id = str(uuid.uuid4())

        # 2. 핸들러 인스턴스 생성 (관계 관리를 위해 self 전달)
        handler = SubscriptionHandler(
            subscription_id, subscription_request, relation_manager=self
        )

        # 상태 변경 통보 (SUBSCRIBED)
        await self.add_relation(
            from_node=from_node if from_node else "unknown",
            to_node="ncof",
            msg_type="SUBSCRIBED",
            data=jsonable_encoder(subscription_request),
            sub_id=subscription_id,
        )

        # 3. 핸들러 시작 (비동기 작업 수행: 외부 NF 구독 등)
        await handler.start()

        # 4. 관리 목록에 추가
        self.subscriptions[subscription_id] = handler

        logger.info(f"새로운 구독 생성 완료 - {subscription_id}")

        return subscription_id

    async def delete_subscription(self, subscription_id: str) -> bool:
        """
        구독을 해지하고 관련 리소스를 정리한다.

        Args:
            subscription_id (str): 삭제할 구독 ID

        Returns:
            bool: 삭제 성공 여부
        """
        handler = self.subscriptions[subscription_id]
        if handler is None:
            logger.warning(f"[{subscription_id}] 삭제하려는 구독 ID가 존재하지 않음")
            return False

        nf_id = self.get_nf_id(handler.subscription)

        from_node = self._get_from_node(nf_id)

        await self.add_relation(
            sub_id=subscription_id,
            from_node=from_node if from_node else "unknown",
            to_node="ncof",
            msg_type="UNSUBSCRIBE",
            data="{}",
        )

        await self.add_relation(
            sub_id=subscription_id,
            from_node="ncof",
            to_node="ncof",
            msg_type="ANALYZED",
            data="{}",
        )

        # if subscription_id in self.subscriptions:
        handler = self.subscriptions.pop(subscription_id)
        # 핸들러 중지 (외부 NF 구독 해지 등)
        await handler.stop()
        # 관련 관계 제거
        await self.remove_relations_by_sub_id(subscription_id)
        logger.info(f"[{subscription_id}] 구독 삭제 완료")
        return True

    async def update_subscription(
        self, subscription_id: str, subscription_request: NncofEventsSubscription
    ) -> bool:
        """
        기존 구독 정보를 업데이트한다.

        Args:
            subscription_id (str): 업데이트할 구독 ID
            subscription_request (NncofEventsSubscription): 변경된 구독 정보

        Returns:
            bool: 업데이트 성공 여부
        """
        if subscription_id not in self.subscriptions:
            logger.warning(
                f"[SubscriptionManager] 업데이트하려는 구독 ID가 존재하지 않음: {subscription_id}"
            )
            return False

        # 기존 핸들러 중지
        await self.delete_subscription(subscription_id)

        # 동일한 ID로 핸들러 재생성 (관계 관리를 위해 self 전달)
        handler = SubscriptionHandler(
            subscription_id, subscription_request, relation_manager=self
        )
        await handler.start()
        self.subscriptions[subscription_id] = handler

        return True

    def get_subscription(
        self, subscription_id: str
    ) -> Optional[NncofEventsSubscription]:
        """
        특정 구독 정보를 조회한다.

        Args:
            subscription_id (str): 조회할 구독 ID

        Returns:
            Optional[NncofEventsSubscription]: 구독 정보
        """
        handler = self.subscriptions.get(subscription_id)
        if handler:
            return handler.subscription
        return None

    def get_handler(self, subscription_id: str) -> Optional[SubscriptionHandler]:
        """
        구독 ID에 해당하는 핸들러 객체를 반환한다.

        Args:
            subscription_id (str): 구독 ID

        Returns:
            Optional[SubscriptionHandler]: 핸들러 객체
        """
        return self.subscriptions.get(subscription_id)

    async def add_relation(
        self, from_node: str, to_node: str, msg_type: str, data: Any, sub_id: str
    ):
        """구독 관계를 추가하고 웹 소켓에 브로드캐스트한다."""
        relation = {
            "from": from_node,
            "to": to_node,
            "type": msg_type,
            "data": data,
            "sub_id": sub_id,
        }

        # 1. 관리 목록에 추가 (SUBSCRIBED 또는 NOTIFY 등의 상태 업데이트가 아닌 순수 SUBSCRIBE 관계만 유지하고 싶을 수 있으나, 일단 모든 이벤트를 기록)
        # 특정 타입만 리스트에 유지하려면 아래에 조건문 추가 가능
        self.active_relations.append(relation)

        # 2. 웹 소켓 브로드캐스트 일원화
        await broadcast_web_message(
            sub_id=sub_id,
            from_node=from_node,
            to_node=to_node,
            msg_type=msg_type,
            data=data,
        )

        logger.info(f"{from_node} ---> {to_node} ({msg_type})")

    async def remove_relations_by_sub_id(self, sub_id: str):
        """특정 구독 ID와 관련된 모든 관계를 제거한다."""
        # 1. 제거될 관계들을 먼저 찾아서 브로드캐스트
        removed_relations = [
            r
            for r in self.active_relations
            if r.get("sub_id") == sub_id or r.get("sub_id") == sub_id + "_nef"
        ]

        for rel in removed_relations:

            await broadcast_web_message(
                from_node=rel["from"],
                to_node=rel["to"],
                msg_type="UNSUBSCRIBED",
                sub_id=sub_id,
                data=json.dumps({"subscriptionId": sub_id}),
            )

            # just for NEF visualization
            if rel["to"] == "nef":
                await broadcast_web_message(
                    from_node=rel["from"],
                    to_node=rel["to"],
                    msg_type="UNSUBSCRIBED",
                    sub_id=sub_id + "_nef",
                    data=json.dumps({"subscriptionId": sub_id}),
                )

        # 2. 리스트에서 제거
        before_count = len(self.active_relations)
        self.active_relations = [
            r for r in self.active_relations if r.get("sub_id") != sub_id
        ]
        self.active_relations = [
            r for r in self.active_relations if r.get("sub_id") != sub_id + "_nef"
        ]

        after_count = len(self.active_relations)
        logger.info(
            f"[SubscriptionManager] Relation 제거: {sub_id} (개수: {before_count} -> {after_count})"
        )

    def get_active_relations(self):
        """현재 모든 활성 구독 관계를 반환한다."""
        return self.active_relations

    def get_handlers(self) -> List[Dict[str, Any]]:
        """
        모든 핸들러의 상태와 기본 구독 정보를 반환한다.
        (웹 대시보드용)

        Returns:
            [{
                "subscription_id": str,
                "is_running": bool,
                "source_nf_type": str | None,
                "event_subscriptions": [{"event": str}, ...],
                "notification_uri": str | None,
                "notif_corr_id": str | None,
                "external_subscriptions": [{"target": str, "external_sub_id": str}, ...]
            }, ...]
        """
        result = []
        for sub_id, handler in self.subscriptions.items():
            source_nf = handler.get_source_nf_type()
            event_subs = []
            if handler.subscription.event_subscriptions:
                for es in handler.subscription.event_subscriptions:
                    event_subs.append({"event": es.event})
            ext_subs = [
                {"target": ext["target"], "external_sub_id": ext["external_sub_id"]}
                for ext in handler.external_subscriptions
            ]
            result.append(
                {
                    "subscription_id": handler.subscription_id,
                    "is_running": handler.is_running,
                    "source_nf_type": source_nf,
                    "event_subscriptions": event_subs,
                    "notification_uri": handler.subscription.notification_uri,
                    "notif_corr_id": handler.subscription.notif_corr_id,
                    "external_subscriptions": ext_subs,
                }
            )
        return result

    def get_subscriptions(self):
        """현재 모든 활성 구독을 반환한다. (내부 구독 + 외부 NF로 보낸 구독 요청 포함)"""
        results = []
        for sub_id, handler in self.subscriptions.items():
            entry = _normalize_subscription(handler.subscription, sub_id)
            ext_subs = []
            for ext in handler.get_external_subscriptions():
                ext_entry: Dict[str, Any] = {
                    "target": ext["target"],
                    "externalSubId": ext["external_sub_id"],
                }
                req_body = ext.get("subscription")
                if req_body is not None:
                    ext_entry["subscription"] = _normalize_subscription(
                        req_body, ext.get("external_sub_id")
                    )
                ext_subs.append(ext_entry)
            entry["externalSubscriptions"] = ext_subs
            results.append(entry)
        return results

    def get_notifications(self) -> Dict[str, Any]:
        """
        모든 핸들러가 수집한 Notification 데이터를 반환한다.

        Returns:
            { subscription_id: { source_nf: { data_type: [ {content, received_at}, ... ] } } }
        """
        result: Dict[str, Any] = {}
        for sub_id, handler in self.subscriptions.items():
            data = handler.notif_data_store.get_all()
            if data:
                result[sub_id] = jsonable_encoder(data)
        return result

    def get_control_notifications(self) -> Dict[str, Any]:
        """
        모든 핸들러가 수집한 Notification (Control) 데이터를 반환한다.
        """
        result: Dict[str, Any] = {}
        for sub_id, handler in self.subscriptions.items():
            data = handler.control_data_store.get_all()
            if data:
                result[sub_id] = jsonable_encoder(data)
        return result

    def get_notification_by_id(self, sub_id: str) -> Dict[str, Any]:
        """
        특정 구독 ID의 Notification 데이터를 반환한다.

        Returns:
            { source_nf: { data_type: [ {content, received_at}, ... ] } }
        """
        handler = self.subscriptions.get(sub_id)
        if handler is None:
            return {}
        data = handler.notif_data_store.get_all()
        return jsonable_encoder(data) if data else {}
