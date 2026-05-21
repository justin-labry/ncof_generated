# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, StrictStr
from typing import Any, List
from typing_extensions import Annotated
from nupf.models.patch_item import PatchItem
from nupf.models.patch_result import PatchResult
from nupf.models.problem_details import ProblemDetails
from nupf.models.redirect_response import RedirectResponse
from nupf.security_api import get_token_oAuth2ClientCredentials

class BaseDefaultApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDefaultApi.subclasses = BaseDefaultApi.subclasses + (cls,)
    async def delete_subscription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="Unique ID of the subscription to be deleted")],
    ) -> None:
        ...


    async def modify_subscription(
        self,
        subscriptionId: Annotated[StrictStr, Field(description="Unique ID of the subscription to be modified")],
        patch_item: Annotated[List[PatchItem], Field(min_length=1)],
    ) -> PatchResult:
        ...
