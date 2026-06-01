# coding: utf-8

import logging
import json

from fastapi import HTTPException

from nncof.apis.nef_events_notifications_api_base import (
    BaseNEFEventExposureNotificationCallbackReceiverApi,
)
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif
from nncof.core.subscription_manager import SubscriptionManager
from nncof.core.websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)


class NefEventsNotificationsApiImpl(
    BaseNEFEventExposureNotificationCallbackReceiverApi
):
    """
    Implementation for NEF Events Notifications API
    """

    async def receive_nef_event_exposure_notif(
        self,
        nf_type: str,
        sub_id: str,
        notif_data: NefEventExposureNotif,
    ) -> None:

        manager = SubscriptionManager()
        handler = manager.get_handler(sub_id)

        if not handler:
            logger.warning(f"[{sub_id}] 구독 핸들러를 찾을 수 없습니다.")
            # 404를 반환하거나 무시할 수 있음. 여기서는 404 처리.
            raise HTTPException(
                status_code=404, detail=f"Subscription {sub_id} not found"
            )

        try:
            # 핸들러를 통해 수신된 데이터 저장
            handler.handle_notification(nf_type, notif_data)

            # ext_sub = handler.get_external_subscription_by_target(sub_id)
            from_node = nf_type

            # 웹 소켓을 통해 실시간 알림 브로드캐스트
            await broadcast_web_message(
                sub_id=sub_id,
                from_node=from_node,
                to_node="ncof",
                msg_type="NOTIFICATION",
                data=json.dumps({"subscriptionId": sub_id}),
            )

        except Exception as e:
            logger.error(f"NEF 알림 처리 중 오류 발생: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error processing notification: {str(e)}"
            )
