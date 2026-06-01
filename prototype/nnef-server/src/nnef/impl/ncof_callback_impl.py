from rich.pretty import pprint
from rich import print
from typing import Any, List
from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)

from nncof_cb.apis.ncof_events_subscription_notification_callback_receiver_api_base import (
    BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi,
)


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
        print("\n[bold blue]===== BEGIN =====[/bold blue]")
        print(f"**** NF: {type.upper()} ****")

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
            print("데이터를 참조하는 중에 문제가 발생했거나, 데이터가 None입니다.")
            print(f"에러 메시지: {e}")  # ex) 'NoneType' object has no attribute ...
            NCOFEventNotificationImpl.cell_power_state = None

        print(f"cell_power_state: ***{NCOFEventNotificationImpl.cell_power_state}***")

        print("[bold blue]===== END =====[/bold blue]\n")
        return None
