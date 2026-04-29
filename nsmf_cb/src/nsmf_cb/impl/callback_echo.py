import json
from typing import Any

from nsmf_cb.apis.smf_event_exposure_notification_callback_receiver_api_base import (
    BaseSMFEventExposureNotificationCallbackReceiverApi,
)


class CallbackEchoImpl(BaseSMFEventExposureNotificationCallbackReceiverApi):
    async def receive_nsmf_event_exposure_notification(self, nsmf_event_exposure_notification: Any) -> None:
        print("\n===== callback/nsmf/notifications =====")
        print(json.dumps(nsmf_event_exposure_notification, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return None

