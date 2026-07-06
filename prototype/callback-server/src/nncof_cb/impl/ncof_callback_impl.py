from rich.pretty import pprint
from rich import print

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
        notification: NncofEventsSubscriptionNotification,
    ) -> None:
        # Add color code below print statement
        print("\n[bold blue]===== BEGIN =====[/bold blue]")
        print(f"**** NF Type: {type.upper()} ****")
        pprint(notification)
        print("[bold blue]===== END =====[/bold blue]\n")
        return None
