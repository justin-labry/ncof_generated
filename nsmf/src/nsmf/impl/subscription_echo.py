import json
from typing import Any

from nsmf.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
from nsmf.models.nsmf_event_exposure import NsmfEventExposure


class SubscriptionEchoImpl(BaseSubscriptionsCollectionApi):
    async def create_individual_subcription(
        self,
        nsmf_event_exposure: NsmfEventExposure,
    ) -> NsmfEventExposure:
        payload: Any = nsmf_event_exposure.to_dict()
        print("\n===== api/nsmf subscription create =====")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return nsmf_event_exposure
