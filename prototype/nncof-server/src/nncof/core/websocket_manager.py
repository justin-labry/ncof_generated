import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket
from nncof.core import utils

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected. Total: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"WebSocket client disconnected. Total: {len(self.active_connections)}"
            )

    async def broadcast(self, message: Dict[str, Any]):
        """
        모든 연결된 클라이언트에게 JSON 메시지를 브로드캐스트합니다.
        """
        if not self.active_connections:
            return

        message_str = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting to a connection: {e}")
                # 연결이 끊긴 경우 disconnect가 호출될 것이므로 여기서 직접 제거하지 않음


# 전역 매니저 인스턴스
manager = ConnectionManager()


async def broadcast_web_message(
    sub_id: str, from_node: str, to_node: str, msg_type: str, data: str
):
    """
    웹 대시보드 클라이언트들에게 메시지를 전송하는 공통 함수
    """
    message = {
        "sub_id": sub_id,
        "from": from_node,
        "to": to_node,
        "type": msg_type,
        "data": data or "{}",
        "timestamp": utils.get_current_timestamp(),
    }
    await manager.broadcast(message)
