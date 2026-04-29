# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Any
from typing_extensions import Annotated
from nsmf.models.event_notification import EventNotification
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nsmf.models.problem_details import ProblemDetails
from nsmf.models.redirect_response import RedirectResponse
from nsmf.security_api import get_token_oAuth2ClientCredentials

class BaseIndividualSubscriptionDocumentApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseIndividualSubscriptionDocumentApi.subclasses = BaseIndividualSubscriptionDocumentApi.subclasses + (cls,)
    async def delete_individual_subcription(
        self,
        subId: Annotated[StrictStr, Field(description="Event Subscription ID")],
    ) -> EventNotification:
        ...


    async def get_individual_subcription(
        self,
        subId: Annotated[StrictStr, Field(description="Event Subscription ID")],
    ) -> NsmfEventExposure:
        ...


    async def replace_individual_subcription(
        self,
        subId: Annotated[StrictStr, Field(description="Event Subscription ID")],
        nsmf_event_exposure: NsmfEventExposure,
    ) -> NsmfEventExposure:
        ...
