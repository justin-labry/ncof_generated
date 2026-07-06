# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.models.problem_details import ProblemDetails
from nnef.security_api import get_token_oAuth2ClientCredentials

class BaseSubscriptionsCollectionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseSubscriptionsCollectionApi.subclasses = BaseSubscriptionsCollectionApi.subclasses + (cls,)
    async def create_individual_subcription(
        self,
        nef_event_exposure_subsc: NefEventExposureSubsc,
    ) -> NefEventExposureSubsc:
        ...
