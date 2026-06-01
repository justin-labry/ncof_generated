from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import logging
import json
import time

from nncof.core import utils
from nncof.core.websocket_manager import manager, broadcast_web_message
from nncof.core.subscription_manager import SubscriptionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["web-api"])


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
    """
    웹 대시보드를 위한 서버 상태 확인 엔드포인트
    """
    return {
        "status": "online",
        "service": "NCOF Event Exposure Service",
        "version": "0.1.0",
    }


@router.get("/events/summary")
async def get_events_summary():
    """
    이벤트 요약 정보 반환 (샘플 데이터)
    """
    return {"total_subscriptions": 5, "active_events": 12, "recent_notifications": 45}


@router.get("/subscriptions/relations")
async def get_subscription_relations():
    """
    현재 활성화된 모든 구독 관계(토폴로지 표시용)를 조회한다.
    반환 형식: [{from, to, type, data, sub_id}]
    """
    manager = SubscriptionManager()
    return manager.get_active_relations()


@router.get("/subscriptions/all")
async def get_subscriptions():
    """
    현재 활성화된 모든 구독을 조회한다.
    반환 형식: [{sub_id, sub_info}]
    """
    manager = SubscriptionManager()
    return manager.get_subscriptions()


@router.get("/notifications/all")
async def get_notifications():
    """
    모든 핸들러가 수집한 Notification 데이터를 조회한다.
    반환 형식: { subscription_id: { source_nf: { data_type: [entries] } } }
    """
    manager = SubscriptionManager()
    return manager.get_notifications()


@router.get("/notifications/{sub_id}")
async def get_notification_by_id(sub_id: str):
    """
    특정 구독 ID의 Notification 데이터를 조회한다.
    반환 형식: { source_nf: { data_type: [entries] } }
    """
    manager = SubscriptionManager()
    return manager.get_notification_by_id(sub_id)


@router.get("/controls/all")
async def get_control_notifications():
    manager = SubscriptionManager()
    return manager.get_control_notifications()
