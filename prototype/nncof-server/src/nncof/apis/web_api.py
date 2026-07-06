import importlib
import logging
import pkgutil

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from nncof.apis.web_api_base import BaseWebApi
from nncof.core.websocket_manager import manager
import nncof.impl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["web-api"])

ns_pkg = nncof.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.get("/status")
async def get_status():
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_status()


@router.get("/subscriptions/relations")
async def get_subscription_relations():
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_subscription_relations()


@router.get("/subscriptions/all")
async def get_subscriptions():
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_subscriptions()


@router.get("/notifications/all")
async def get_notifications():
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_notifications()


@router.get("/notifications/{sub_id}")
async def get_notification_by_id(sub_id: str):
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_notification_by_id(sub_id)


@router.get("/controls/all")
async def get_control_notifications():
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_control_notifications()


@router.get("/handlers")
async def get_handlers():
    if not BaseWebApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseWebApi.subclasses[0]().get_handlers()
