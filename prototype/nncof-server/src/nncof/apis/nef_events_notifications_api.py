# coding: utf-8

import importlib
import pkgutil

# from nncof.apis.upf_events_notifications_api_base import BaseNCOFEventsNotificationsApi
from nncof.apis.nef_events_notifications_api_base import (
    BaseNEFEventExposureNotificationCallbackReceiverApi,
)
import nncof.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    HTTPException,
)

from nncof.models.problem_details import ProblemDetails
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif
from nnef.models.redirect_response import RedirectResponse

router = APIRouter()

ns_pkg = nncof.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/notifications/{nf_type}/{sub_id}",
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
    tags=["NEF Event Exposure Notification (Callback Receiver)"],
    summary="Receive a notification (NefEventExposureNotif)",
    response_model_by_alias=True,
)
async def receive_nef_event_exposure_notif(
    nf_type: str,
    sub_id: str,
    nncof_events_notification: NefEventExposureNotif = Body(None, description=""),
) -> None:
    if not BaseNEFEventExposureNotificationCallbackReceiverApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseNEFEventExposureNotificationCallbackReceiverApi.subclasses[
        0
    ]().receive_nef_event_exposure_notif(nf_type, sub_id, nncof_events_notification)
