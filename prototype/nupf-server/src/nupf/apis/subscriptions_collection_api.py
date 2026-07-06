# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from nupf.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
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
from typing import Any
from nupf.models.create_event_subscription import CreateEventSubscription
from nupf.models.created_event_subscription import CreatedEventSubscription
from nupf.models.problem_details import ProblemDetails
from nupf.models.redirect_response import RedirectResponse
from nupf.security_api import get_token_oAuth2ClientCredentials

router = APIRouter()

ns_pkg = nupf.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/ee-subscriptions",
    responses={
        201: {
            "model": CreatedEventSubscription,
            "description": "Successful creation of an UPF Event Subscription",
        },
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
        501: {"model": ProblemDetails, "description": "Not Implemented"},
        502: {"model": ProblemDetails, "description": "Bad Gateway"},
        503: {"model": ProblemDetails, "description": "Service Unavailable"},
        "default": {"description": "Generic Error"},
    },
    tags=["Subscriptions (Collection)"],
    summary="Nupf_EventExposure Subscribe service Operation",
    response_model_by_alias=True,
)
async def create_subscription(
    create_event_subscription: CreateEventSubscription = Body(None, description=""),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nupf-ee"]
    ),
) -> CreatedEventSubscription:
    if not BaseSubscriptionsCollectionApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseSubscriptionsCollectionApi.subclasses[0]().create_subscription(
        create_event_subscription
    )
