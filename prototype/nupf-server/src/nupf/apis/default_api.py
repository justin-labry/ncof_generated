# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from nupf.apis.default_api_base import BaseDefaultApi
import nupf.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from nupf.models.extra_models import TokenModel  # noqa: F401
from pydantic import Field, StrictStr
from typing import Any, List
from typing_extensions import Annotated
from nupf.models.patch_item import PatchItem
from nupf.models.patch_result import PatchResult
from nupf.models.problem_details import ProblemDetails
from nupf.models.redirect_response import RedirectResponse
from nupf.security_api import get_token_oAuth2ClientCredentials

router = APIRouter()

ns_pkg = nupf.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.delete(
    "/ee-subscriptions/{subscriptionId}",
    responses={
        204: {"description": "Subsription deleted successfully"},
        307: {"model": RedirectResponse, "description": "Temporary Redirect"},
        308: {"model": RedirectResponse, "description": "Permanent Redirect"},
        400: {"model": ProblemDetails, "description": "Bad request"},
        401: {"model": ProblemDetails, "description": "Unauthorized"},
        403: {"model": ProblemDetails, "description": "Forbidden"},
        404: {"model": ProblemDetails, "description": "Not Found"},
        411: {"model": ProblemDetails, "description": "Length Required"},
        413: {"model": ProblemDetails, "description": "Content Too Large"},
        415: {"model": ProblemDetails, "description": "Unsupported Media Type"},
        429: {"model": ProblemDetails, "description": "Too Many Requests"},
        500: {"model": ProblemDetails, "description": "Internal Server Error"},
        502: {"model": ProblemDetails, "description": "Bad Gateway"},
        503: {"model": ProblemDetails, "description": "Service Unavailable"},
        "default": {"description": "Generic Error"},
    },
    tags=["default"],
    summary="Nupf_EventExposure UnSubscribe service Operation",
    response_model_by_alias=True,
)
async def delete_subscription(
    subscriptionId: Annotated[StrictStr, Field(description="Unique ID of the subscription to be deleted")] = Path(..., description="Unique ID of the subscription to be deleted"),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nupf-ee"]
    ),
) -> None:
    if not BaseDefaultApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseDefaultApi.subclasses[0]().delete_subscription(subscriptionId)


@router.patch(
    "/ee-subscriptions/{subscriptionId}",
    responses={
        200: {"model": PatchResult, "description": "Expected response to a valid request"},
        204: {"description": "Successful response"},
        307: {"model": RedirectResponse, "description": "Temporary Redirect"},
        308: {"model": RedirectResponse, "description": "Permanent Redirect"},
        400: {"model": ProblemDetails, "description": "Bad request"},
        401: {"model": ProblemDetails, "description": "Unauthorized"},
        403: {"model": ProblemDetails, "description": "Forbidden"},
        404: {"model": ProblemDetails, "description": "Not Found"},
        411: {"model": ProblemDetails, "description": "Length Required"},
        413: {"model": ProblemDetails, "description": "Content Too Large"},
        415: {"model": ProblemDetails, "description": "Unsupported Media Type"},
        429: {"model": ProblemDetails, "description": "Too Many Requests"},
        500: {"model": ProblemDetails, "description": "Internal Server Error"},
        502: {"model": ProblemDetails, "description": "Bad Gateway"},
        503: {"model": ProblemDetails, "description": "Service Unavailable"},
        "default": {"description": "Generic Error"},
    },
    tags=["default"],
    summary="Nupf_EventExposure Subscribe Modify service Operation",
    response_model_by_alias=True,
)
async def modify_subscription(
    subscriptionId: Annotated[StrictStr, Field(description="Unique ID of the subscription to be modified")] = Path(..., description="Unique ID of the subscription to be modified"),
    patch_item: Annotated[List[PatchItem], Field(min_length=1)] = Body(None, description=""),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nupf-ee"]
    ),
) -> PatchResult:
    if not BaseDefaultApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseDefaultApi.subclasses[0]().modify_subscription(subscriptionId, patch_item)
