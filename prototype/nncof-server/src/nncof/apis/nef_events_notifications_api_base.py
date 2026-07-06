# coding: utf-8

from typing import ClassVar, Tuple  # noqa: F401

from nnef.models.nef_event_exposure_notif import NefEventExposureNotif


class BaseNEFEventExposureNotificationCallbackReceiverApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseNEFEventExposureNotificationCallbackReceiverApi.subclasses = (
            BaseNEFEventExposureNotificationCallbackReceiverApi.subclasses + (cls,)
        )

    async def receive_nef_event_exposure_notif(
        self,
        sub_id: str,
        notif_data: NefEventExposureNotif,
    ) -> None: ...
