# 저장 구독 복원 경로 테스트
#
# main.py 에서 restore_persisted_subscriptions() 를 다시 켜기 전까지 이 함수에는
# 테스트가 하나도 없었다. 여기서 다루는 것은 셋이다.
#   1. 만료된 저장 구독도 하위 NF 구독을 해지한 뒤 버려야 한다 (안 하면 영구 고아)
#   2. 유효한 저장 구독은 이전 하위 구독을 해지한 뒤 재구독해야 한다
#   3. 복원 도중의 상태 저장이 아직 복원하지 않은 항목을 지우면 안 된다
#
# 네트워크는 전부 대역으로 막는다 — 실제 NF 나 장비로 요청이 나가지 않는다.

import asyncio
import json
import time

import pytest

from nncof.core import subscription_handler as sh_module
from nncof.core.subscription_handler import SubscriptionHandler
from nncof.core.subscription_manager import SubscriptionManager


def _saved_subscription(notification_uri: str, mon_dur: str) -> dict:
    return {
        "notificationURI": notification_uri,
        "notifCorrId": "NOTIFICATION_2026-03-01T12:00:00+09:00_1",
        "consNfInfo": {"nfId": "pcf-uuid-001"},
        "evtReq": {"monDur": mon_dur, "repPeriod": 60},
        "eventSubscriptions": [{"event": "QOS_POLICY_ASSIST"}],
    }


_LIVE = "2030-01-01T00:00:00+09:00"
_EXPIRED = "2020-01-01T00:00:00+09:00"
_DEVICE_NOTIF_ID = "NOTIFICATION_upf_2026-09-09T19:17:29.044648+09:00"


def _state(entries: dict) -> dict:
    return {"schema_version": 1, "subscriptions": entries}


def _entry(mon_dur: str, external_ids: list[tuple[str, str]]) -> dict:
    return {
        "subscription": _saved_subscription("http://10.254.173.46:55555/", mon_dur),
        "notifications": [],
        "control_notifications": [],
        "external_subscriptions": [
            {"target": target, "external_sub_id": ext_id, "subscription": None}
            for target, ext_id in external_ids
        ],
    }


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """상태 파일을 tmp 로 돌린 새 SubscriptionManager (싱글턴 초기화 포함)."""
    monkeypatch.setenv("NCOF_STATE_FILE", str(tmp_path / "state.json"))
    SubscriptionManager._instance = None
    created = SubscriptionManager()
    yield created
    SubscriptionManager._instance = None


@pytest.fixture
def traced(monkeypatch):
    """하위 NF 로 나가는 구독/해지를 전부 가로채 호출 순서를 기록한다."""
    calls: list[tuple[str, str]] = []

    async def fake_subscribe(self, target, req_body):
        calls.append(("SUBSCRIBE", target))
        return f"new-{target}"

    async def fake_unsubscribe(self, target, external_sub_id):
        calls.append(("UNSUBSCRIBE", external_sub_id))
        return True

    monkeypatch.setattr(
        SubscriptionHandler, "_send_external_subscription", fake_subscribe
    )
    monkeypatch.setattr(
        SubscriptionHandler, "_send_external_unsubscription", fake_unsubscribe
    )
    monkeypatch.setattr(
        sh_module,
        "build_subscription_requests",
        lambda sub_id, sub: [
            {"target": "smf", "subscription": {"notifId": _DEVICE_NOTIF_ID}}
        ],
    )
    return calls


def _write(manager, state):
    manager._state_store.path.parent.mkdir(parents=True, exist_ok=True)
    manager._state_store.path.write_text(json.dumps(state), encoding="utf-8")


def _read(manager) -> dict:
    return json.loads(manager._state_store.path.read_text(encoding="utf-8"))


def test_expired_subscription_is_torn_down_before_being_dropped(manager, traced):
    """만료 저장 구독을 그냥 버리면 하위 구독이 영구 고아가 된다."""
    _write(manager, _state({"expired-sub": _entry(_EXPIRED, [("smf", _DEVICE_NOTIF_ID)])}))

    asyncio.run(manager.restore_persisted_subscriptions())

    assert ("UNSUBSCRIBE", _DEVICE_NOTIF_ID) in traced, "만료 구독의 하위 구독을 해지하지 않았다"
    assert ("SUBSCRIBE", "smf") not in traced, "만료 구독을 복원해 버렸다"
    assert manager.subscriptions == {}
    assert _read(manager)["subscriptions"] == {}


def test_restored_subscription_unsubscribes_stale_before_resubscribing(manager, traced):
    """유효한 저장 구독은 이전 하위 구독을 먼저 해지한 뒤 재구독해야 한다."""
    _write(manager, _state({"live-sub": _entry(_LIVE, [("smf", _DEVICE_NOTIF_ID)])}))

    asyncio.run(manager.restore_persisted_subscriptions())

    assert traced == [
        ("UNSUBSCRIBE", _DEVICE_NOTIF_ID),
        ("SUBSCRIBE", "smf"),
    ], f"해지가 재구독보다 먼저 오지 않았다: {traced}"
    assert "live-sub" in manager.subscriptions
    stored = _read(manager)["subscriptions"]["live-sub"]["external_subscriptions"]
    assert [item["external_sub_id"] for item in stored] == ["new-smf"]


def test_persist_during_restore_keeps_untouched_entries(manager, traced):
    """복원 도중의 저장이 아직 복원하지 않은 항목을 지우면 안 된다.

    통지 수신·제어 발송·서버 종료가 전부 persist_state 를 부르고, 복원은
    이제 백그라운드로 돌기 때문에 이 저장이 복원 중간에 끼어든다.
    """
    _write(
        manager,
        _state(
            {
                "sub-a": _entry(_LIVE, [("smf", "old-a")]),
                "sub-b": _entry(_LIVE, [("smf", "old-b")]),
            }
        ),
    )

    seen: list[list[str]] = []
    original_start = SubscriptionHandler.start

    async def start_then_persist(self, *args, **kwargs):
        await original_start(self, *args, **kwargs)
        # 복원 도중에 끼어든 저장을 흉내낸다.
        await manager.persist_state()
        seen.append(sorted(_read(manager)["subscriptions"]))

    SubscriptionHandler.start = start_then_persist
    try:
        asyncio.run(manager.restore_persisted_subscriptions())
    finally:
        SubscriptionHandler.start = original_start

    assert seen[0] == ["sub-a", "sub-b"], (
        f"첫 항목 복원 직후의 저장이 미복원 항목을 지웠다: {seen}"
    )
    assert sorted(_read(manager)["subscriptions"]) == ["sub-a", "sub-b"]


def test_restore_asks_start_to_skip_the_cosmetic_delays(manager, traced):
    """복원 경로는 GUI 연출 대기를 끄고 start() 를 부른다.

    켜 두면 구독 1건당 4~6초가 기동 시간에 얹혀 hypercorn 기동 타임아웃까지
    밀어올린다. 그 인자를 실제로 넘기는지 여기서 고정한다.
    """
    seen: list[bool] = []
    original_start = SubscriptionHandler.start

    async def capture(self, stagger_relations: bool = True):
        seen.append(stagger_relations)
        await original_start(self, stagger_relations=stagger_relations)

    SubscriptionHandler.start = capture
    try:
        _write(manager, _state({"live-sub": _entry(_LIVE, [])}))
        asyncio.run(manager.restore_persisted_subscriptions())
    finally:
        SubscriptionHandler.start = original_start

    assert seen == [False], f"복원이 연출 대기를 끄지 않았다: {seen}"


class _RelationSpy:
    def __init__(self):
        self.added = 0

    async def add_relation(self, **kwargs):
        self.added += 1

    async def remove_relations_by_sub_id(self, sub_id):
        pass


class _NoEvtReq:
    """evt_req 가 없어 분석 태스크를 띄우지 않는 최소 구독 대역."""

    evt_req = None


def test_start_without_stagger_does_not_sleep(monkeypatch):
    """stagger_relations=False 는 실제로 대기를 건너뛴다 (연출은 그대로 수행)."""
    handler = object.__new__(SubscriptionHandler)
    handler.subscription_id = "ncof-subscription"
    handler.subscription = _NoEvtReq()
    handler._relation_manager = _RelationSpy()
    handler._on_state_change = None
    handler._stale_external_subscriptions = []
    handler.external_subscriptions = []
    handler.is_running = False

    async def fake_subscribe(target, req_body):
        return f"new-{target}"

    handler._send_external_subscription = fake_subscribe
    monkeypatch.setattr(
        sh_module,
        "build_subscription_requests",
        lambda sub_id, sub: [
            {"target": "af", "subscription": {"notifId": _DEVICE_NOTIF_ID}},
            {"target": "smf", "subscription": {"notifId": _DEVICE_NOTIF_ID}},
        ],
    )

    started = time.monotonic()
    asyncio.run(handler.start(stagger_relations=False))
    elapsed = time.monotonic() - started

    # 켜져 있으면 sleep(1) + 대상별 sleep(0.5) 로 최소 2초가 걸린다.
    assert elapsed < 0.5, f"연출 대기를 건너뛰지 않았다 ({elapsed:.2f}s)"
    # 대기만 건너뛰고 relation 자체는 그대로 등록해야 한다 (af 는 2건, smf 는 1건).
    assert handler._relation_manager.added == 3
    assert [item["external_sub_id"] for item in handler.external_subscriptions] == [
        "new-af",
        "new-smf",
    ]
