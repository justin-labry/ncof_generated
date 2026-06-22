# coding: utf-8
import os
from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from nnef.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
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
from typing import Any
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.models.problem_details import ProblemDetails
from nnef.security_api import get_token_oAuth2ClientCredentials

router = APIRouter()

ns_pkg = nnef.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/nnef-eventexposure/{type}/v1/subscriptions",
    responses={
        201: {"model": NefEventExposureSubsc, "description": "Success"},
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
    summary="subscribe to notifications",
    response_model_by_alias=True,
)
async def create_individual_subcription(
    nef_event_exposure_subsc: NefEventExposureSubsc = Body(None, description=""),
    type: str = Path(..., description="NF service type"),
    token_oAuth2ClientCredentials: TokenModel = Security(
        get_token_oAuth2ClientCredentials, scopes=["nnef-eventexposure"]
    ),
) -> NefEventExposureSubsc:
    if not BaseSubscriptionsCollectionApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    # return await BaseSubscriptionsCollectionApi.subclasses[0]().create_individual_subcription(nef_event_exposure_subsc)

    # 1. 실행 시 주입된 환경 변수 확인 (기본값 TYPE_A)
    # app_mode = os.getenv("APP_MODE", "AF").upper()
    app_mode = type.upper()

    print(f"***** app mode: {app_mode}")
    # 2. 모드에 맞는 구현체 찾기
    # 클래스 이름이나 별도 속성을 통해 매핑할 수 있습니다.
    target_cls = None
    for cls in BaseSubscriptionsCollectionApi.subclasses:
        if app_mode == "AF" and cls.__name__ == "AFImpl":
            target_cls = cls
            break
        elif app_mode == "RICF" and cls.__name__ == "RICFImpl":
            target_cls = cls
            break

    # 3. 일치하는 모드가 없으면 첫 번째 구현체 사용 또는 에러 처리
    if not target_cls:
        target_cls = BaseSubscriptionsCollectionApi.subclasses[0]

    return await target_cls().create_individual_subcription(nef_event_exposure_subsc)
