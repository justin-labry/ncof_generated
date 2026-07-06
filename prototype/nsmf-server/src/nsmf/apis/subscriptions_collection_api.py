# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from nsmf.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
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
from typing import Any
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nsmf.models.problem_details import ProblemDetails
from nsmf.security_api import get_token_oAuth2ClientCredentials

router = APIRouter()

ns_pkg = nsmf.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/subscriptions",
    responses={
        201: {"model": NsmfEventExposure, "description": "Created."},
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
    tags=["Subscriptions (Collection)"],
    summary="Create an individual subscription for event notifications from the SMF",
    response_model_by_alias=True,
)
async def create_individual_subcription(
    nsmf_event_exposure: NsmfEventExposure = Body(None, description=""),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nsmf-event-exposure"]
    ),
) -> NsmfEventExposure:
    if not BaseSubscriptionsCollectionApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseSubscriptionsCollectionApi.subclasses[0]().create_individual_subcription(nsmf_event_exposure)
