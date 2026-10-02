# coding: utf-8

import logging
from rich.pretty import pretty_repr
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

            logger.info(f"[UPF] --- [NOTIFICATION] ---> [NCOF]")
            logger.info("\n%s", pretty_repr(notif_data, expand_all=True))

            printKPI(notif_data)

            # 핸들러를 통해 수신된 데이터 저장
            await handler.handle_notification("UPF", notif_data)

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

def printKPI(notif_data: NotificationData):
    logger.info("[KPI]")
    for notif_item in notif_data.notification_items:
        if notif_item is None:
            continue

        if notif_item.qos_monitoring_measurement is not None:
            ue_ipv4_addr = notif_item.ue_ipv4_addr
            dl_packet_delay = notif_item.qos_monitoring_measurement.dl_packet_delay # type: ignore
            ul_packet_delay = notif_item.qos_monitoring_measurement.ul_packet_delay # type: ignore
            dl_max_packet_delay = notif_item.qos_monitoring_measurement.dl_max_packet_delay # type: ignore
            ul_max_packet_delay = notif_item.qos_monitoring_measurement.ul_max_packet_delay  # type: ignore
            dl_ave_throughput = notif_item.qos_monitoring_measurement.dl_ave_throughput  # type: ignore
            ul_ave_throughput = notif_item.qos_monitoring_measurement.ul_ave_throughput  # type: ignore
            packet_loss_rate = notif_item.qos_monitoring_measurement.packet_loss_rate  # type: ignore
            jitter = notif_item.qos_monitoring_measurement.jitter  # type: ignore


            logger.info(f"Input data related to QoS flow {ue_ipv4_addr}")
            logger.info(f"""
                    - DL average packet delay of UE <---> CN: {dl_packet_delay}
                    - UL average packet delay of UE <---> CN: {ul_packet_delay}
                    - DL maximum packet delay of UE <---> CN: {dl_max_packet_delay}
                    - UL maximum packet delay of UE <---> CN: {ul_max_packet_delay}
                    - DL average throughput of UE <---> CN: {dl_ave_throughput}
                    - UL average throughput of UE <---> CN: {ul_ave_throughput}
                    - Packet loss rate of UE <---> CN: {packet_loss_rate}
                    - Jitter of UE <---> CN: {jitter}
            """)

    # print only 12_c_NotificationData_from_UPF_to_NCOF_v1.0.json
    if len(notif_data.notification_items) != 1:
        return
    for notif_item in notif_data.notification_items:
        if notif_item is None:
            continue
        if notif_item.user_data_usage_measurements is not None:
            logger.info(f"""Input data related to Non-3GPP access""")
            dl_average_throughput = notif_item.user_data_usage_measurements[1].throughput_statistics_measurement.dl_average_throughput # type: ignore
            ul_average_throughput = notif_item.user_data_usage_measurements[0].throughput_statistics_measurement.ul_average_throughput # type: ignore
            logger.info(f"""
                    - DL background traffic rate of Non-3GPP access switch <---> CN: {dl_average_throughput}
                    - UL background traffic rate of Non-3GPP access switch <---> CN: {ul_average_throughput}
            """)
