import json
from typing import Any

from nupf_cb.apis.upf_event_exposure_notification_callback_receiver_api_base import (
    BaseUPFEventExposureNotificationCallbackReceiverApi,
)


class CallbackEchoImpl(BaseUPFEventExposureNotificationCallbackReceiverApi):
    async def receive_upf_event_notification(self, body: Any) -> None:
        print("\n===== callback/nupf/notifications =====")
        print(json.dumps(body, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return None

