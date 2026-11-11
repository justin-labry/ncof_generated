import asyncio
import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket
from nncof.core import utils

logger = logging.getLogger(__name__)

# 대시보드 연결 하나에 보내기를 기다리는 상한(초). 읽지 않는 대시보드(송신 버퍼 가득)에 막히면 broadcast 를 await 하는
# UPF/NEF 통지 처리기의 응답이 멈추고, 상대가 기다리다 연결을 닫으면 hypercorn h2 연결이 안 닫혀 fd 가 새며
# 종료(부모 SIGTERM)도 막힌다(10/28 E2E 재현 — HANDOFF 「NCOF fd 누수 · 종료 행」 과 같은 모양).
_SEND_TIMEOUT_SEC = 1.0


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._closing: set[asyncio.Task] = set()

    async def _close_dropped(self, websocket: WebSocket) -> None:
        # 1013 Try Again Later — 대시보드(nncof-ui useWebSocket.ts onclose)가 다시 붙는다. 닫기 프레임도 같은 송신 버퍼
        # 뒤에 서므로 기다림에 상한을 둔다(상대가 전혀 읽지 않으면 TCP 는 남는다 — 정지 전 탭 닫기는 그대로 필요).
        try:
            await asyncio.wait_for(websocket.close(code=1013), 10)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"막힌 대시보드 연결 닫기: {type(e).__name__} {e}")

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

        async def send(connection: WebSocket) -> None:
            try:
                await asyncio.wait_for(connection.send_text(message_str), _SEND_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                if connection not in self.active_connections:
                    return  # 같은 순간 돈 다른 broadcast 가 이미 뺐다 — 로그 · 닫기는 한 번만
                logger.error(f"대시보드 연결이 {_SEND_TIMEOUT_SEC}초 넘게 받지 않음 — 이 연결은 닫고 더 보내지 않는다")
                self.disconnect(connection)
                # 목록에서만 빼면 브라우저는 열린 채 갱신이 멈춘다(onclose 가 안 와 다시 붙지 않음) — 닫기를 보낸다
                task = asyncio.create_task(self._close_dropped(connection))
                self._closing.add(task)
                task.add_done_callback(self._closing.discard)
            except Exception as e:
                logger.error(f"Error broadcasting to a connection: {e}")
                # 연결이 끊긴 경우 disconnect가 호출될 것이므로 여기서 직접 제거하지 않음

        # 연결마다 동시에 보낸다 — 막힌 대시보드가 여럿이어도 통지 처리기가 기다리는 상한은 1초
        await asyncio.gather(*(send(c) for c in list(self.active_connections)))


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
