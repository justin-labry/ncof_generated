import json
from typing import Any

from nnef.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc


class SubscriptionEchoImpl(BaseSubscriptionsCollectionApi):
    async def create_individual_subcription(
        self,
        nef_event_exposure_subsc: NefEventExposureSubsc,
    ) -> NefEventExposureSubsc:
        payload: Any = nef_event_exposure_subsc.to_dict()
        print("\n===== api/nnef subscription create =====")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return nef_event_exposure_subsc
