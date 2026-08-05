# JSON 영속 저장소와 Notify 데이터 저장소를 검증하는 테스트

import asyncio

from nncof.core.data_store import NotificationDataStore
from nncof.core.persistence_store import JsonStateStore


def test_json_state_store_round_trip(tmp_path):
    state_path = tmp_path / "ncof_state.json"
    store = JsonStateStore(state_path)
    expected = {"schema_version": 1, "subscriptions": {"sub-1": {"value": 1}}}

    asyncio.run(store.save(expected))

    assert store.load() == expected


def test_json_state_store_quarantines_invalid_file(tmp_path):
    state_path = tmp_path / "ncof_state.json"
    state_path.write_text("not-json", encoding="utf-8")

    state = JsonStateStore(state_path).load()

    assert state == {"schema_version": 1, "subscriptions": {}}
    assert state_path.with_suffix(".json.corrupt").exists()


def test_notification_data_store_preserves_source_in_export_and_restore():
    store = NotificationDataStore()
    store.add_data("UPF", "notif-1", {"value": 1})

    restored_store = NotificationDataStore()
    restored_store.restore_state(store.export_state())

    assert restored_store.get_all() == {"notif-1": {"value": 1}}
    assert restored_store.export_state() == [
        {"source_nf": "UPF", "notif_id": "notif-1", "data": {"value": 1}}
    ]
