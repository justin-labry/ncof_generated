from datetime import datetime
from typing import Dict

from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif

from nupf.models.notification_data import NotificationData


class NotificationDataStore:
    """
    여러 NF로부터 수집된 다양한 종류의 데이터를 효율적으로 관리하기 위한 클래스이다.
    데이터는 notifcation id 별로 저장된다.
    """

    def __init__(self):
        self._data = {}
        self._last_updated = datetime.now()

    def add_data(
        self,
        target_nf: str,
        notif_id: str | None,
        data: (
            NncofEventsSubscriptionNotification
            | NotificationData
            | NefEventExposureNotif
            | Dict
            | None
        ),
    ):
        """
        데이터를 notif_id 별로 저장한다.

        """

        self._data[notif_id] = data

        self._last_updated = datetime.now()
        # logger.debug(
        #     f"[DataStore] 데이터 추가됨 - Source: {source_nf}, Type: {data_type} (현재 개수: {len(target_list)})"
        # )

    def get_all(
        self,
    ) -> dict[
        str,
        NncofEventsSubscriptionNotification
        | NotificationData
        | NefEventExposureNotif
        | None,
    ]:
        return self._data

    def get_all_2(
        self,
    ) -> Dict[
        str,
        Dict[
            str,
            # List[
            NncofEventsSubscriptionNotification
            | NotificationData
            | NefEventExposureNotif,
            # ],
        ],
    ]:
        """모든 수집 데이터를 반환한다."""
        # return dict(self._data)
        return self._data

    def clear(self):
        """데이터를 초기화한다."""
        self._data.clear()

    def is_empty(self) -> bool:
        """데이터가 비어있는지 확인한다."""
        return len(self._data) == 0
