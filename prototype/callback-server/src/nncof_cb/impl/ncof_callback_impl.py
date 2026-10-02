
import logging
from rich.pretty import pretty_repr

from typing import List

logger = logging.getLogger(__name__)

from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)

from nncof_cb.apis.ncof_events_subscription_notification_callback_receiver_api_base import (
    BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi,
)

class NCOFEventNotificationImpl(
    BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi
):
    async def receive_ncof_events_subscription_notification(
        self,
        type: str,
        notification: List[NncofEventsSubscriptionNotification],
    ) -> None:
        logger.info(f"[NCOF] --- [NOTIFICATION] ---> [{type.upper()}]")
        for item in notification:
            logger.info("\n%s", pretty_repr(item, expand_all=True))

            qos_param_sets = (item
                            .event_notifications[0] # type: ignore
                            .qos_pol_assist_infos[0]
                            .qos_pol_assist_info[0]
                            .qos_pol_assist_sets
                        #  .qos_param_set # type: ignore
                        )

            flow_desc = (item
                        .event_notifications[0] # type: ignore
                        .qos_pol_assist_infos[0].qos_pol_assist_info[0].qos_pol_assist_sets[0].f_descs # type: ignore
                        )
            # logger.info(f"flow description: {flow_desc}")

            # if flow_desc is not None:
            #     for flow in flow_desc:
            #         logger.info(f"FLOW.IP_TRAFFIC_FILTER: {flow.ip_traffic_filter}")

            # logger.info(f"GBR/MBR 을 다음으로 설정 하겠음")
            # for set in qos_param_sets:
            #     logger.info(f"GBR_DL: {set.qos_param_set.gbr_dl}, MBR_DL: {set.qos_param_set.mbr_dl}")  #type: ignore

            logger.info(f"PCF drives to change the DL GBR/MBR of QoS flows as: ")
            for set in qos_param_sets:
                logger.info(f"DL GBR/MBR of QoS flow 192.168.101.XXX:XXXXX:  {set.qos_param_set.gbr_dl} /  {set.qos_param_set.mbr_dl} ")  #type: ignore

        return None
