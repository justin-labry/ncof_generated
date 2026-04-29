import json
from typing import Any

from nncof.apis.ncof_events_subscriptions_collection_api_base import (
    BaseNCOFEventsSubscriptionsCollectionApi,
)
from nncof.models.nncof_events_subscription import NncofEventsSubscription


class SubscriptionEchoImpl(BaseNCOFEventsSubscriptionsCollectionApi):
    async def create_ncof_events_subscription(
        self,
        nncof_events_subscription: NncofEventsSubscription,
    ) -> NncofEventsSubscription:
        payload: Any = nncof_events_subscription.to_dict()
        print("\n===== api/nncof subscription create =====")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return nncof_events_subscription

