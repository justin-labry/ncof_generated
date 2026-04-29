import json
from typing import Any

from nupf.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
from nupf.models.create_event_subscription import CreateEventSubscription
from nupf.models.created_event_subscription import CreatedEventSubscription


class SubscriptionEchoImpl(BaseSubscriptionsCollectionApi):
    async def create_subscription(
        self,
        create_event_subscription: CreateEventSubscription,
    ) -> CreatedEventSubscription:
        payload: Any = create_event_subscription.to_dict()
        print("\n===== api/nupf subscription create =====")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print("===== END =====\n")
        return CreatedEventSubscription(
            subscription=create_event_subscription.subscription,
            subscriptionId="https://example.com/api/nupf/subscriptions/sub-001",
            supportedFeatures=create_event_subscription.supported_features,
        )

