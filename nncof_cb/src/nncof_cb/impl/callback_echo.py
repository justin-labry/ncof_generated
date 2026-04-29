import json
from typing import Any

from nncof_cb.apis.ncof_events_subscription_notification_callback_receiver_api_base import (
    BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi,
)


class CallbackEchoImpl(BaseNCOFEventsSubscriptionNotificationCallbackReceiverApi):
    async def receive_ncof_events_subscription_notification(
        self,
        nncof_events_subscription_notification: Any,
    ) -> None:
        print("\n===== callback/nncof/notifications =====")
        print(json.dumps(nncof_events_subscription_notification, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return None

