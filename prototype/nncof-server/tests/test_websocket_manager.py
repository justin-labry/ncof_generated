# 대시보드 websocket broadcast 가 읽지 않는 연결에 무한정 막히지 않는지 검증하는 테스트

import asyncio
import time

from nncof.core import websocket_manager


class _Stuck:
    def __init__(self):
        self.closed: int | None = None

    async def send_text(self, text):
        await asyncio.Event().wait()  # 송신 버퍼가 가득 찬 대시보드

    async def close(self, code: int = 1000):
        self.closed = code


class _Reader:
    def __init__(self):
        self.got: list[str] = []

    async def send_text(self, text):
        self.got.append(text)


def test_broadcast_drops_and_closes_a_dashboard_that_does_not_read(monkeypatch, caplog):
    """막힌 연결은 상한 뒤 빠지고(닫기 1013 — 대시보드가 다시 붙는다) 다른 연결은 계속 받는다 —
    broadcast 를 await 하는 통지 처리기가 응답을 돌려줄 수 있게."""
    monkeypatch.setattr(websocket_manager, "_SEND_TIMEOUT_SEC", 0.05)
    manager = websocket_manager.ConnectionManager()
    stuck, reader = _Stuck(), _Reader()
    manager.active_connections = [stuck, reader]

    async def run():
        await asyncio.wait_for(manager.broadcast({"type": "NOTIFICATION"}), 1.0)
        await asyncio.wait_for(manager.broadcast({"type": "NOTIFICATION"}), 1.0)
        await asyncio.gather(*list(manager._closing))

    with caplog.at_level("ERROR"):
        asyncio.run(run())
    assert manager.active_connections == [reader]
    assert len(reader.got) == 2
    assert stuck.closed == 1013
    assert caplog.text.count("넘게 받지 않음") == 1


def test_several_stuck_dashboards_cost_one_timeout_not_n(monkeypatch, caplog):
    """막힌 연결이 여럿이어도 연결마다 동시에 기다린다 — 통지 응답 지연 상한은 1번의 상한. 동시 broadcast 여럿이어도 로그는 연결당 한 번."""
    monkeypatch.setattr(websocket_manager, "_SEND_TIMEOUT_SEC", 0.2)
    manager = websocket_manager.ConnectionManager()
    stucks = [_Stuck() for _ in range(3)]
    reader = _Reader()
    manager.active_connections = [*stucks, reader]

    async def run():
        start = time.monotonic()
        await asyncio.gather(*(manager.broadcast({"type": "N"}) for _ in range(4)))
        elapsed = time.monotonic() - start
        await asyncio.gather(*list(manager._closing))
        return elapsed

    with caplog.at_level("ERROR"):
        elapsed = asyncio.run(run())
    assert elapsed < 0.5  # 순서대로였다면 0.6초 이상
    assert manager.active_connections == [reader] and len(reader.got) == 4
    assert caplog.text.count("넘게 받지 않음") == 3
    assert all(s.closed == 1013 for s in stucks)
