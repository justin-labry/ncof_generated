# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from nsmf.apis.individual_subscription_document_api_base import (
    BaseIndividualSubscriptionDocumentApi,
)
import nsmf.impl

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

from nsmf.models.extra_models import TokenModel  # noqa: F401
from pydantic import Field, StrictStr
from typing import Any
from typing_extensions import Annotated
from nsmf.models.event_notification import EventNotification
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nsmf.models.problem_details import ProblemDetails
from nsmf.models.redirect_response import RedirectResponse
from nsmf.security_api import get_token_oAuth2ClientCredentials

router = APIRouter()

ns_pkg = nsmf.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/subscriptions/{subId}",
    responses={
        200: {
            "model": NsmfEventExposure,
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
    summary="Read an individual subscription for event notifications from the SMF",
    response_model_by_alias=True,
)
async def get_individual_subcription(
    subId: Annotated[StrictStr, Field(description="Event Subscription ID")] = Path(
        ..., description="Event Subscription ID"
    ),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nsmf-event-exposure"]
    ),
) -> NsmfEventExposure:
    if not BaseIndividualSubscriptionDocumentApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseIndividualSubscriptionDocumentApi.subclasses[
        0
    ]().get_individual_subcription(subId)


@router.put(
    "/subscriptions/{subId}",
    responses={
        200: {
            "model": NsmfEventExposure,
            "description": "OK. Resource was successfully modified and representation is returned",
        },
        204: {"description": "No Content. Resource was successfully modified"},
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
    summary="Replace an individual subscription for event notifications from the SMF",
    response_model_by_alias=True,
)
async def replace_individual_subcription(
    subId: Annotated[StrictStr, Field(description="Event Subscription ID")] = Path(
        ..., description="Event Subscription ID"
    ),
    nsmf_event_exposure: NsmfEventExposure = Body(None, description=""),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nsmf-event-exposure"]
    ),
) -> NsmfEventExposure:
    if not BaseIndividualSubscriptionDocumentApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseIndividualSubscriptionDocumentApi.subclasses[
        0
    ]().replace_individual_subcription(subId, nsmf_event_exposure)


@router.delete(
    "/subscriptions/{subId}",
    responses={
        200: {
            "model": EventNotification,
            "description": "OK. Resource was successfully deleted and representation is returned",
        },
        204: {"description": "No Content. Resource was successfully deleted"},
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
    summary="Delete an individual subscription for event notifications from the SMF",
    response_model_by_alias=True,
)
async def delete_individual_subcription(
    subId: Annotated[StrictStr, Field(description="Event Subscription ID")] = Path(
        ..., description="Event Subscription ID"
    ),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nsmf-event-exposure"]
    ),
) -> NsmfEventExposure:
    if not BaseIndividualSubscriptionDocumentApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseIndividualSubscriptionDocumentApi.subclasses[
        0
    ]().delete_individual_subcription(subId)
