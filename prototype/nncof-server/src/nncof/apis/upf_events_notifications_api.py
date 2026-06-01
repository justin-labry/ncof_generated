# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

# from nncof.apis.ncof_events_subscriptions_collection_api_base import BaseNCOFEventsSubscriptionsCollectionApi
from nncof.apis.upf_events_notifications_api_base import (
    BaseUPFEventExposureNotificationCallbackReceiverApi,
)
import nncof.impl

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

from nncof.models.extra_models import TokenModel  # noqa: F401
from typing import Any
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.problem_details import ProblemDetails
from nncof.security_api import get_token_oAuth2ClientCredentials

from nupf.models.notification_data import NotificationData
from nupf.models.redirect_response import RedirectResponse

router = APIRouter()

ns_pkg = nncof.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/notifications/upf/{sub_id}",
    responses={
        204: {"description": "The receipt of the Notification is acknowledged."},
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
        200: {"description": "Generic Error"},
    },
    tags=["UPF Event Exposure Notification (Callback Receiver)"],
    summary="Receive a notification (ExtNotificationData)",
    response_model_by_alias=True,
)
async def receive_upf_event_notification(
    sub_id: str,
    notif_data: NotificationData = Body(None, description=""),
) -> None:
    if not BaseUPFEventExposureNotificationCallbackReceiverApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseUPFEventExposureNotificationCallbackReceiverApi.subclasses[
        0
    ]().receive_upf_event_notification(sub_id, notif_data)
