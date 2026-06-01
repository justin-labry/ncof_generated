# coding: utf-8

import os
from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from nnef.apis.individual_subscription_document_api_base import (
    BaseIndividualSubscriptionDocumentApi,
)
import nnef.impl

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

from nnef.models.extra_models import TokenModel  # noqa: F401
from pydantic import Field, StrictStr, field_validator
from typing import Any, Optional
from typing_extensions import Annotated
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.models.problem_details import ProblemDetails
from nnef.models.redirect_response import RedirectResponse
from nnef.security_api import get_token_oAuth2ClientCredentials

router = APIRouter()

ns_pkg = nnef.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/subscriptions/{subscriptionId}",
    responses={
        200: {
            "model": NefEventExposureSubsc,
            "description": "OK. Resource representation is returned",
        },
        307: {"model": RedirectResponse, "description": "Temporary Redirect"},
        308: {"model": RedirectResponse, "description": "Permanent Redirect"},
        400: {"model": ProblemDetails, "description": "Bad request"},
        401: {"model": ProblemDetails, "description": "Unauthorized"},
        403: {"model": ProblemDetails, "description": "Forbidden"},
        404: {"model": ProblemDetails, "description": "Not Found"},
        406: {"description": "406 Not Acceptable"},
        429: {"model": ProblemDetails, "description": "Too Many Requests"},
        500: {"model": ProblemDetails, "description": "Internal Server Error"},
        502: {"model": ProblemDetails, "description": "Bad Gateway"},
        503: {"model": ProblemDetails, "description": "Service Unavailable"},
        "default": {"description": "Generic Error"},
    },
    tags=["IndividualSubscription (Document)"],
    summary="retrieve subscription",
    response_model_by_alias=True,
)
async def get_individual_subcription(
    subscriptionId: Annotated[
        StrictStr, Field(description="Event Subscription ID")
    ] = Path(..., description="Event Subscription ID"),
    supp_feat: Annotated[
        Optional[Annotated[str, Field(strict=True)]],
        Field(description="Features supported by the NF service consumer"),
    ] = Query(
        None,
        description="Features supported by the NF service consumer",
        alias="supp-feat",
        pattern=r"/^[A-Fa-f0-9]*$/",
    ),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nnef-eventexposure"]
    ),
) -> NefEventExposureSubsc:
    if not BaseIndividualSubscriptionDocumentApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseIndividualSubscriptionDocumentApi.subclasses[
        0
    ]().get_individual_subcription(subscriptionId, supp_feat)


@router.put(
    "/subscriptions/{subscriptionId}",
    responses={
        200: {
            "model": NefEventExposureSubsc,
            "description": "OK. Resource was succesfully modified and representation is returned",
        },
        204: {"description": "No Content. Resource was succesfully modified"},
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
    tags=["IndividualSubscription (Document)"],
    summary="update subscription",
    response_model_by_alias=True,
)
async def replace_individual_subcription(
    subscriptionId: Annotated[
        StrictStr, Field(description="Event Subscription ID")
    ] = Path(..., description="Event Subscription ID"),
    nef_event_exposure_subsc: NefEventExposureSubsc = Body(None, description=""),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nnef-eventexposure"]
    ),
) -> NefEventExposureSubsc:
    if not BaseIndividualSubscriptionDocumentApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseIndividualSubscriptionDocumentApi.subclasses[
        0
    ]().replace_individual_subcription(subscriptionId, nef_event_exposure_subsc)


@router.delete(
    "/subscriptions/{subscriptionId}",
    responses={
        204: {"description": "No Content. Resource was succesfully deleted"},
        307: {"model": RedirectResponse, "description": "Temporary Redirect"},
        308: {"model": RedirectResponse, "description": "Permanent Redirect"},
        400: {"model": ProblemDetails, "description": "Bad request"},
        401: {"model": ProblemDetails, "description": "Unauthorized"},
        403: {"model": ProblemDetails, "description": "Forbidden"},
        404: {"model": ProblemDetails, "description": "Not Found"},
        429: {"model": ProblemDetails, "description": "Too Many Requests"},
        500: {"model": ProblemDetails, "description": "Internal Server Error"},
        502: {"model": ProblemDetails, "description": "Bad Gateway"},
        503: {"model": ProblemDetails, "description": "Service Unavailable"},
        "default": {"description": "Generic Error"},
    },
    tags=["IndividualSubscription (Document)"],
    summary="unsubscribe from notifications",
    response_model_by_alias=True,
)
async def delete_individual_subcription(
    subscriptionId: Annotated[
        StrictStr, Field(description="Event Subscription ID")
    ] = Path(..., description="Event Subscription ID"),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nnef-eventexposure"]
    ),
) -> None:

    app_mode = os.getenv("APP_MODE", "AF").upper()
    target_cls = None
    for cls in BaseIndividualSubscriptionDocumentApi.subclasses:
        if app_mode == "AF" and cls.__name__ == "AFIndividualSubscriptionDocumentApi":
            target_cls = cls
            break
        elif (
            app_mode == "RICF"
            and cls.__name__ == "RICFIndividualSubscriptionDocumentApi"
        ):
            target_cls = cls
            break

    if not target_cls:
        raise HTTPException(500, "Cannot load implementation")

    return await target_cls().delete_individual_subcription(subscriptionId)
