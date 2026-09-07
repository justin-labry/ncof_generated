
import logging
from rich.pretty import pretty_repr

from typing import List

logger = logging.getLogger(__name__)

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
        notification: List[NncofEventsSubscriptionNotification],
    ) -> None:
        logger.info(f"[NCOF] --- [NOTIFICATION] ---> [{type.upper()}]")
        for item in notification:
            logger.info("\n%s", pretty_repr(item, expand_all=True))
        return None
