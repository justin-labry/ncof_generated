# gNB2 판정 하나가 PCF(14_e)·RICF(15f) 구독에 같은 순간 나가는지 검증하는 테스트

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nncof.core import data_analyzer
from nncof.core.data_analyzer import DataAnalyzer
from nncof.core.data_store import NotificationDataStore
from nncof.models.nncof_events_subscription import NncofEventsSubscription

_CLIENT_DIR = Path(__file__).resolve().parents[2] / "api-clients"
_T0 = datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)


class _Perf:
    def to_dict(self) -> dict:
        return {}


@pytest.fixture(autouse=True)
def _reset_shared_state(monkeypatch):
    monkeypatch.setattr(data_analyzer, "_shared_engine", None)
    monkeypatch.setattr(data_analyzer, "_active_analyzers", [])
    monkeypatch.setattr(data_analyzer, "_last_sample_ts", None)


def _analyzer(json_name: str, sent: list) -> DataAnalyzer:
    payload = json.loads((_CLIENT_DIR / json_name).read_text(encoding="utf-8"))
    subscription = NncofEventsSubscription.from_dict(payload)
    analyzer: DataAnalyzer

    async def notify(nf_type: str, event: list[dict]) -> None:
        sent.append((analyzer.subscription_id, nf_type, event))

    analyzer = DataAnalyzer(
        subscription_id=f"sub-{json_name}",
        subscription=subscription,
        notif_data_store=NotificationDataStore(),
        control_data_store=NotificationDataStore(),
        notify_callback=notify,
    )
    analyzer.sample_ts = _T0
    analyzer._get_wlan_performance_data = lambda: (_Perf(), analyzer.sample_ts)
    analyzer.is_running = True
    data_analyzer._active_analyzers.append(analyzer)
    return analyzer


def _tick(analyzer: DataAnalyzer, monkeypatch, metric: float, age_sec: int = 0) -> None:
    """age_sec: 이번 틱이 읽는 UPF 샘플의 timeStamp 를 _T0 + age_sec 로 둔다."""
    analyzer.sample_ts = _T0 + timedelta(seconds=age_sec)
    monkeypatch.setattr(data_analyzer, "extract_wlan_dl_mbps", lambda _: metric)
    asyncio.run(analyzer._analyze_and_generate(analyzer.get_source_nf_type()))


def _cell_state(event: list[dict]) -> str:
    info = event[0]["eventNotifications"][0]["_cellPowerCtrlOptInfos"][0]
    return info["_cellPowerCtrlInfos"][0]["_cellPowerParamSets"][0][
        "_cellPowerParamSet"
    ]["_cellPowerState"]


def _gbr_dl(event: list[dict]) -> list[str]:
    info = event[0]["eventNotifications"][0]["qosPolAssistInfos"][0]
    return [
        s["qosParamSet"]["gbrDl"] for s in info["qosPolAssistInfo"][0]["qosPolAssistSets"]
    ]


def test_one_tick_sends_deep_sleep_and_nr_off_to_both(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)

    _tick(pcf, monkeypatch, metric=50.0)  # < 500 Mbps → DEEP_SLEEP

    by_nf = {nf: (sub_id, event) for sub_id, nf, event in sent}
    assert set(by_nf) == {"pcf", "ricf"}
    assert by_nf["ricf"][0] == ricf.subscription_id
    assert _cell_state(by_nf["ricf"][1]) == "DEEP_SLEEP"
    assert by_nf["pcf"][0] == pcf.subscription_id
    assert "0.0 Mbps" in _gbr_dl(by_nf["pcf"][1])  # NR gNB2 세트가 꺼짐
    assert by_nf["pcf"][1][0]["subscriptionId"] == pcf.subscription_id
    assert by_nf["ricf"][1][0]["subscriptionId"] == ricf.subscription_id


def test_other_analyzer_tick_with_same_state_sends_nothing(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)

    _tick(pcf, monkeypatch, metric=50.0)
    sent.clear()
    _tick(ricf, monkeypatch, metric=40.0, age_sec=20)  # 여전히 DEEP_SLEEP

    assert sent == []


def test_state_change_on_ricf_tick_also_updates_pcf(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)

    _tick(pcf, monkeypatch, metric=50.0)
    sent.clear()
    _tick(ricf, monkeypatch, metric=550.0, age_sec=20)  # ≥ 500 Mbps → ACTIVE

    by_nf = {nf: event for _, nf, event in sent}
    assert _cell_state(by_nf["ricf"]) == "ACTIVE"
    assert "0.0 Mbps" not in _gbr_dl(by_nf["pcf"])


def test_late_subscription_gets_current_state_once(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    _tick(pcf, monkeypatch, metric=50.0)
    sent.clear()

    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _tick(pcf, monkeypatch, metric=50.0, age_sec=20)

    assert [(sub_id, nf) for sub_id, nf, _ in sent] == [(ricf.subscription_id, "ricf")]
    assert _cell_state(sent[0][2]) == "DEEP_SLEEP"


def test_last_analyzer_leaving_resets_shared_engine(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _tick(pcf, monkeypatch, metric=50.0)
    engine = data_analyzer._shared_engine

    ricf._leave_active_analyzers()
    assert data_analyzer._shared_engine is engine  # PCF 가 아직 사용 중
    pcf._leave_active_analyzers()
    assert data_analyzer._shared_engine is None
    assert data_analyzer._active_analyzers == []


def test_older_sample_does_not_revert_state(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)

    _tick(pcf, monkeypatch, metric=50.0, age_sec=20)  # 새 샘플 → DEEP_SLEEP
    sent.clear()
    _tick(ricf, monkeypatch, metric=550.0, age_sec=5)  # 그보다 옛 샘플(ACTIVE 값)

    assert sent == []
    assert data_analyzer._shared_engine.last_emitted_state == "DEEP_SLEEP"


def test_late_subscription_gets_state_even_without_new_sample(monkeypatch):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    _tick(pcf, monkeypatch, metric=50.0, age_sec=20)
    sent.clear()

    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _tick(pcf, monkeypatch, metric=550.0, age_sec=5)  # 옛 샘플 → 판정 생략, 현재 상태만 전달

    assert [(nf, _cell_state(ev)) for _, nf, ev in sent] == [("ricf", "DEEP_SLEEP")]


def test_sample_is_newest_across_all_active_subscriptions():
    from nupf.models.notification_data import NotificationData

    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    del pcf._get_wlan_performance_data, ricf._get_wlan_performance_data

    template = json.loads(
        (Path(data_analyzer.__file__).parent / "12p_c_NotificationData_from_UPF_to_NCOF_v1.0.json")
        .read_text(encoding="utf-8")
    )

    def upf(ts: datetime) -> NotificationData:
        notif = NotificationData.from_dict(template)
        for item in notif.notification_items:
            item.time_stamp = ts
        return notif

    old, new = upf(_T0), upf(_T0 + timedelta(seconds=9))
    pcf.notif_data_store.add_data("upf", "pcf-stream", old)
    ricf.notif_data_store.add_data("upf", "ricf-stream", new)

    # PCF 의 틱이라도 RICF 구독 store 의 더 새 샘플을 쓴다
    assert pcf._get_wlan_performance_data() == (new, _T0 + timedelta(seconds=9))
