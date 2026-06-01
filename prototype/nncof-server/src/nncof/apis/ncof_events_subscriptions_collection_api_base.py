# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.problem_details import ProblemDetails
from nncof.security_api import get_token_oAuth2ClientCredentials

class BaseNCOFEventsSubscriptionsCollectionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseNCOFEventsSubscriptionsCollectionApi.subclasses = BaseNCOFEventsSubscriptionsCollectionApi.subclasses + (cls,)
    async def create_ncof_events_subscription(
        self,
        nncof_events_subscription: NncofEventsSubscription,
    ) -> NncofEventsSubscription:
        ...
