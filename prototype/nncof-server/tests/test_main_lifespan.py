# 저장 구독 복원이 서버 기동을 막지 않는지 검증하는 테스트
#
# 복원은 구독 1건마다 하위 NF 재구독과 GUI 연출 대기를 거쳐 수 초가 걸린다.
# lifespan 안에서 await 하면 구독이 쌓인 상태 파일에서 hypercorn 기동 타임아웃
# (기본 60초)에 걸려 기동 자체가 실패한다. 그래서 백그라운드 태스크로 분리했고,
# 이 테스트가 그 분리를 고정한다.

import asyncio

import pytest

from nncof import main


class _NeverFinishingManager:
    """복원이 끝나지 않는 구독 관리자 — 기동이 이것을 기다리면 테스트가 실패한다."""

    def __init__(self):
        self.restore_started = asyncio.Event()
        self.restore_finished = False
        # 일어난 순서를 기록한다. 복원 태스크를 회수한 뒤에 shutdown 이 와야 한다 —
        # 그 반대면 shutdown 이 순회하는 dict 를 복원이 계속 늘려 RuntimeError 가 난다.
        self.events: list[str] = []

    async def restore_persisted_subscriptions(self):
        self.restore_started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.events.append("restore_cancelled")
            raise
        self.restore_finished = True

    async def shutdown(self):
        self.events.append("shutdown")


def _install(monkeypatch) -> list:
    created: list[_NeverFinishingManager] = []

    def factory():
        manager = _NeverFinishingManager()
        created.append(manager)
        return manager

    monkeypatch.setattr(main, "SubscriptionManager", factory)
    return created


def test_lifespan_does_not_block_on_restore(monkeypatch):
    created = _install(monkeypatch)
    tasks: list[asyncio.Task] = []

    real_create_task = asyncio.create_task

    def recording_create_task(coro, **kwargs):
        task = real_create_task(coro, **kwargs)
        tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", recording_create_task)

    async def scenario():
        # lifespan 이 복원을 await 하면 __aenter__ 가 끝나지 않아 여기서 타임아웃 난다.
        async with asyncio.timeout(5):
            async with main.lifespan(None):
                manager = created[0]
                await manager.restore_started.wait()
                assert manager.restore_finished is False

            # ⚠️ 반드시 asyncio.run 안에서 확인해야 한다.
            # asyncio.run 은 반환 직전에 남은 태스크를 스스로 취소하므로,
            # 밖에서 확인하면 production 코드가 아니라 인터프리터가 만든 결과를
            # 검증하게 되고 cancel()/await 를 지워도 테스트가 통과한다.
            assert manager.events == ["restore_cancelled", "shutdown"], (
                f"복원 태스크 회수와 shutdown 의 순서가 어긋났다: {manager.events}"
            )
            assert manager.restore_finished is False
            assert tasks and tasks[0].done(), "복원 태스크를 회수하지 않고 떠났다"
        return created[0]

    asyncio.run(scenario())


def test_restore_failure_is_logged_not_swallowed(monkeypatch, caplog):
    """복원이 예외로 죽으면 태스크 안에서 조용히 사라지지 않고 로그로 드러나야 한다."""

    class _FailingManager:
        async def restore_persisted_subscriptions(self):
            raise RuntimeError("상태 파일 폭발")

    with caplog.at_level("ERROR", logger="nncof.main"):
        asyncio.run(main._restore_persisted_subscriptions(_FailingManager()))

    assert any(
        "저장 구독 복원 실패" in record.message for record in caplog.records
    ), "복원 실패가 로그에 남지 않았다"


def test_restore_cancellation_propagates():
    """취소는 삼키지 않고 다시 올려보내야 한다 — 그래야 lifespan 이 회수를 확인할 수 있다."""

    class _SlowManager:
        async def restore_persisted_subscriptions(self):
            await asyncio.sleep(3600)

    async def scenario():
        task = asyncio.create_task(
            main._restore_persisted_subscriptions(_SlowManager())
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
