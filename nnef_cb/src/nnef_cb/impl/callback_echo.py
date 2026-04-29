import json
from typing import Any

from nnef_cb.apis.nef_event_exposure_notification_callback_receiver_api_base import (
    BaseNEFEventExposureNotificationCallbackReceiverApi,
)


class CallbackEchoImpl(BaseNEFEventExposureNotificationCallbackReceiverApi):
    async def receive_nef_event_exposure_notif(self, nef_event_exposure_notif: Any) -> None:
        print("\n===== callback/nnef/notifications =====")
        print(json.dumps(nef_event_exposure_notif, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return None

