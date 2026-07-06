# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Any
from typing_extensions import Annotated
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.problem_details import ProblemDetails
from nncof.models.redirect_response import RedirectResponse
from nncof.security_api import get_token_oAuth2ClientCredentials

class BaseIndividualNCOFEventsSubscriptionDocumentApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseIndividualNCOFEventsSubscriptionDocumentApi.subclasses = BaseIndividualNCOFEventsSubscriptionDocumentApi.subclasses + (cls,)
    async def update_ncof_events_subscription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="String identifying a subscription to the Nncof_EventsSubscription Service.")],
        nncof_events_subscription: NncofEventsSubscription,
    ) -> NncofEventsSubscription:
        ...


    async def delete_ncof_events_subscription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="String identifying a subscription to the Nncof_EventsSubscription Service")],
    ) -> None:
        ...
