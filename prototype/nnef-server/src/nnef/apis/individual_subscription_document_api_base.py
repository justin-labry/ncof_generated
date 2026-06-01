# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr, field_validator
from typing import Any, Optional
from typing_extensions import Annotated
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.models.problem_details import ProblemDetails
from nnef.models.redirect_response import RedirectResponse
from nnef.security_api import get_token_oAuth2ClientCredentials

class BaseIndividualSubscriptionDocumentApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseIndividualSubscriptionDocumentApi.subclasses = BaseIndividualSubscriptionDocumentApi.subclasses + (cls,)
    async def get_individual_subcription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="Event Subscription ID")],
        supp_feat: Annotated[Optional[Annotated[str, Field(strict=True)]], Field(description="Features supported by the NF service consumer")],
    ) -> NefEventExposureSubsc:
        ...


    async def replace_individual_subcription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="Event Subscription ID")],
        nef_event_exposure_subsc: NefEventExposureSubsc,
    ) -> NefEventExposureSubsc:
        ...


    async def delete_individual_subcription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="Event Subscription ID")],
    ) -> None:
        ...
