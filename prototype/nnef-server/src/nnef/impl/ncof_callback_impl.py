import logging
from rich.pretty import pretty_repr

from typing import List

from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)

from nncof_cb.apis.ncof_events_subscription_notification_callback_receiver_api_base import (
    BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi,
)

logger = logging.getLogger(__name__)

class NCOFEventNotificationImpl(
    BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi
):

    cell_power_state = None

    async def receive_ncof_events_subscription_notification(
        self,
        type: str,
        # notification: NncofEventsSubscriptionNotification,
        notifications: List[NncofEventsSubscriptionNotification],
    ) -> None:
        # Add color code below print statement
        logger.info(f"[NCOF] --- [NOTIFICATION] ---> [{type.upper()}]")
        logger.info("\n%s", pretty_repr(notifications[0], expand_all=True))
        if len(notifications) == 0:
            return None

        notification = notifications[0]
        if notification is None:
            return None
        # pprint(notification)

        if notification.event_notifications is None:
            return None

        event_notif = notification.event_notifications[0]

        if event_notif is None:
            return None

        # cell_power_state = None
        # event_notif.cell_power_ctrl_opt_infos[0].cell_power_ctrl_infos[0].cell_power_param_sets[0].spatial_validity.g_ran_node_ids[0].g_nb_id.g_nb_value
        try:
            NCOFEventNotificationImpl.cell_power_state = (
                event_notif.cell_power_ctrl_opt_infos[0]  # type: ignore
                .cell_power_ctrl_infos[0]
                .cell_power_param_sets[0]
                .cell_power_param_set.cell_power_state  # type: ignore
            )
        except (
            AttributeError,
            IndexError,
            TypeError,
        ) as e:  # 💡 TypeError를 반드시 추가해야 합니다!
            logger.warning("데이터를 참조하는 중에 문제가 발생했거나, 데이터가 None입니다.")
            logger.warning(f"에러 메시지: {e}")  # ex) 'NoneType' object has no attribute ...
            NCOFEventNotificationImpl.cell_power_state = None

        # logger.info(f"CELL_POWER_STATE: {NCOFEventNotificationImpl.cell_power_state} 로 설정 하겠음")
        logger.info(f"RICF drives to change the power state of gNB 2: From ACTIVE to {NCOFEventNotificationImpl.cell_power_state} ")
        return None
