# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nsmf.models.problem_details import ProblemDetails
from nsmf.security_api import get_token_oAuth2ClientCredentials

class BaseSubscriptionsCollectionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSubscriptionsCollectionApi.subclasses = BaseSubscriptionsCollectionApi.subclasses + (cls,)
    async def create_individual_subcription(
        self,
        nsmf_event_exposure: NsmfEventExposure,
    ) -> NsmfEventExposure:
        ...
