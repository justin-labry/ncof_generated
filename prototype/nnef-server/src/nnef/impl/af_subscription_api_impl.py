# coding: utf-8

from fastapi import HTTPException
from pydantic import Field, StrictStr
from typing import Optional
from typing_extensions import Annotated

from nnef.apis.individual_subscription_document_api_base import (
    BaseIndividualSubscriptionDocumentApi,
)
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.impl.simulation import subscriptions

import logging

logger = logging.getLogger(__name__)


class AFIndividualSubscriptionDocumentApi(BaseIndividualSubscriptionDocumentApi):

    async def get_individual_subcription(
        self,
        sub_id: Annotated[StrictStr, Field(description="Event Subscription ID")],
        supp_feat: Annotated[
            Optional[Annotated[str, Field(strict=True)]],
            Field(description="Features supported by the NF service consumer"),
        ],
    ) -> NefEventExposureSubsc: ...

    async def replace_individual_subcription(
        self,
        sub_id: Annotated[StrictStr, Field(description="Event Subscription ID")],
        nef_event_exposure_subsc: NefEventExposureSubsc,
    ) -> NefEventExposureSubsc: ...

    async def delete_individual_subcription(
        self,
        sub_id: Annotated[StrictStr, Field(description="Event Subscription ID")],
    ) -> None:
        subscription = subscriptions.pop(sub_id, None)
        if subscription is None:
            raise HTTPException(
                status_code=404,
                detail=f"Subscription not found: {sub_id}",
            )
        logger.info(f"[{sub_id}] ❌ Subscription deleted successfully")
        return subscription["event_subscription"]
