# coding: utf-8

from typing import ClassVar, Tuple  # noqa: F401

from nupf.models.notification_data import NotificationData


class BaseUPFEventExposureNotificationCallbackReceiverApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseUPFEventExposureNotificationCallbackReceiverApi.subclasses = (
            BaseUPFEventExposureNotificationCallbackReceiverApi.subclasses + (cls,)
        )

    async def receive_upf_event_notification(
        self,
        sub_id: str,
        notif_data: NotificationData,
    ) -> None: ...
