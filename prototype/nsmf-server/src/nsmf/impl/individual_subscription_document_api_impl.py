import logging

from fastapi import HTTPException, Response

from nsmf.apis.individual_subscription_document_api_base import (
    BaseIndividualSubscriptionDocumentApi,
)
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nsmf.models.event_notification import EventNotification
from nsmf.impl.subscriptions_collection_api_impl import _subscriptions

logger = logging.getLogger(__name__)


class NCOFEventsIndividualSubscriptionDocumentApiImpl(
    BaseIndividualSubscriptionDocumentApi
):
    async def get_individual_subcription(
        self,
        subId: str,
    ) -> NsmfEventExposure:
        # For now, return a dummy implementation
        # In a real implementation, this would retrieve subscription by ID
        raise HTTPException(status_code=501, detail="Not implemented")

    async def replace_individual_subcription(
        self,
        sub_id: str,
        nsmf_event_exposure: NsmfEventExposure,
    ) -> NsmfEventExposure:
        # For now, return a dummy implementation
        # In a real implementation, this would update subscription by ID
        raise HTTPException(status_code=501, detail="Not implemented")

    async def delete_individual_subcription(
        self,
        sub_id: str,
    ) -> NsmfEventExposure:
        subscription = _subscriptions.pop(sub_id, None)
        if subscription is None:
            raise HTTPException(
                status_code=404,
                detail=f"Subscription not found: {sub_id}",
            )
        logger.info(f"[{sub_id}] ❌ Subscription deleted successfully")
        return subscription["event_subscription"]
