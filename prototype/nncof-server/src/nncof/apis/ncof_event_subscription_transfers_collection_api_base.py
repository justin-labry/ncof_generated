# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from nncof.models.analytics_subscriptions_transfer import AnalyticsSubscriptionsTransfer
from nncof.models.problem_details import ProblemDetails
from nncof.security_api import get_token_oAuth2ClientCredentials

class BaseNCOFEventSubscriptionTransfersCollectionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseNCOFEventSubscriptionTransfersCollectionApi.subclasses = BaseNCOFEventSubscriptionTransfersCollectionApi.subclasses + (cls,)
    async def create_ncof_event_subscription_transfer(
        self,
        analytics_subscriptions_transfer: AnalyticsSubscriptionsTransfer,
    ) -> None:
        ...
