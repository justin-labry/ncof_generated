# coding: utf-8

import logging
from rich.pretty import pretty_repr
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
            logger.warning(f"[{sub_id}] 구독 핸들러를 없음")
            # 404를 반환하거나 무시할 수 있음. 여기서는 404 처리.
            raise HTTPException(
                status_code=404, detail=f"Subscription {sub_id} not found"
            )

        try:

            logger.info(f"[{nf_type.upper()}] --- [NOTIFICATION] ---> [NCOF]")
            logger.info("\n%s", pretty_repr(notif_data, expand_all=True))

            printKPI(notif_data)

            # 핸들러를 통해 수신된 데이터 저장
            await handler.handle_notification(nf_type, notif_data)

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

def printKPI(notif_data: NefEventExposureNotif):
    logger.info("[KPI]")
    event_notif_1 = notif_data.event_notifs[0]

    try:
        if event_notif_1 is not None and event_notif_1.perf_data_infos is not None:

            for perf_data_info in event_notif_1.perf_data_infos:
                ue_ip_addr = perf_data_info.ue_ip_addr

                pdb_dl = perf_data_info.perf_data.pdb_dl  # type: ignore
                delay_ul = perf_data_info.perf_data.delay_ul  # type: ignore
                thrput_dl = perf_data_info.perf_data.thrput_dl  # type: ignore
                thrput_ul = perf_data_info.perf_data.thrput_ul # type: ignore
                plr_dl = perf_data_info.perf_data.plr_dl # type: ignore
                jitter = perf_data_info.perf_data.jitter # type: ignore

                if ue_ip_addr is not None:
                    logger.info(f"Input data related to QoS flow {ue_ip_addr.ipv4_addr}:8554")
                logger.info(f"""
                    - DL average packet delay of UE <---> gNB: {pdb_dl}
                    - UL average packet delay of UE <---> gNB: {delay_ul}
                    - DL average packet delay of UE <---> DN: {pdb_dl}
                    - UL average packet delay of UE <---> DN: {delay_ul}
                    - DL average throughput of UE <---> DN: {thrput_dl}
                    - UL average throughput of UE <---> DN: {thrput_ul}
                    - DL average packet loss rate of UE <---> DN: {plr_dl}
                    - Jitter of UE <---> DN: {jitter}
                """)

        # if event_notif_1 is not None and event_notif_1.rf_signal_infos is not None and len(event_notif_1.rf_signal_infos) > 1:
        if event_notif_1 is not None and event_notif_1.rf_signal_infos is not None:
            for rf_signal_info in event_notif_1.rf_signal_infos:
                supi = rf_signal_info.supi # type: ignore
                logger.info(f"Input data related to SUPI {supi} and gNB 1")
                ue_ip_addr = rf_signal_info.ue_ip_addr # type: ignore
                rsrp = rf_signal_info.rf_signal_data.ref_signal_measurements[0].rsrp # type: ignore
                rsrq = rf_signal_info.rf_signal_data.ref_signal_measurements[0].rsrq # type: ignore
                sinr = rf_signal_info.rf_signal_data.ref_signal_measurements[0].sinr # type: ignore
                bler = rf_signal_info.rf_signal_data.ref_signal_measurements[0].bler # type: ignore
                connectivity = rf_signal_info.rf_signal_data.ref_signal_measurements[0].connectivity # type: ignore

                logger.info(f"""
                    - DL RSRP: {rsrp}
                    - DL RSRQ: {rsrq}
                    - DL SINR: {sinr}
                    - DL BLER: {bler}
                    - DL connectivity: {connectivity}
                """)

    except (AttributeError, IndexError, TypeError) as e:
        print(e)
        pass

    try:
        if len(notif_data.event_notifs) > 1:
            event_notif_2 = notif_data.event_notifs[1]

            if event_notif_2 is not None:
                logger.info(f"Input data related to power consumption")
                power_1 = event_notif_2.power_energy_consumption_infos[0].power_energy_cons_data.power# type: ignore
                power_2 = event_notif_2.power_energy_consumption_infos[1].power_energy_cons_data.power# type: ignore
                logger.info(f"""
                    - Mean power consumption of gNB 1: {power_1}
                    - Mean power consumption of gNB 2: {power_2}
                """)
    except (AttributeError, IndexError, TypeError) as e:
            print(e)
            pass
