# coding: utf-8

import logging
import json

from fastapi import HTTPException

from nncof.apis.upf_events_notifications_api_base import (
    BaseUPFEventExposureNotificationCallbackReceiverApi,
)
from nupf.models.notification_data import NotificationData
from nncof.core.subscription_manager import SubscriptionManager
from nncof.core.websocket_manager import broadcast_web_message

logger = logging.getLogger(__name__)


class UpfEventExposureNotificationCallbackReceiverApiImpl(
    BaseUPFEventExposureNotificationCallbackReceiverApi
):
    """
    Implementation for UPF Events Notifications API
    """

    async def receive_upf_event_notification(
        self,
        sub_id: str,
        notif_data: NotificationData,
    ) -> None:

        manager = SubscriptionManager()
        handler = manager.get_handler(sub_id)

        if not handler:
            logger.warning(f"[{sub_id}] 구독 핸들러를 찾을 수 없습니다.")
            raise HTTPException(
                status_code=404, detail=f"Subscription {sub_id} not found"
            )

        try:
            # 핸들러를 통해 수신된 데이터 저장
            handler.handle_notification("UPF", notif_data)

            # 웹 소켓을 통해 실시간 알림 브로드캐스트
            await broadcast_web_message(
                sub_id=sub_id,
                from_node="upf",
                to_node="ncof",
                msg_type="NOTIFICATION",
                data=json.dumps({"subscriptionId": sub_id}),
            )

        except Exception as e:
            logger.error(f"UPF 알림 처리 중 오류 발생: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error processing notification: {str(e)}"
            )
