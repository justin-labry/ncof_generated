# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from nupf.models.create_event_subscription import CreateEventSubscription
from nupf.models.created_event_subscription import CreatedEventSubscription
from nupf.models.problem_details import ProblemDetails
from nupf.models.redirect_response import RedirectResponse
from nupf.security_api import get_token_oAuth2ClientCredentials

class BaseSubscriptionsCollectionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSubscriptionsCollectionApi.subclasses = BaseSubscriptionsCollectionApi.subclasses + (cls,)
    async def create_subscription(
        self,
        create_event_subscription: CreateEventSubscription,
    ) -> CreatedEventSubscription:
        ...
