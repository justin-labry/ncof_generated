# gNB2 판정(리더 틱 · 12p_c 입력 · 설정 즉시 반영)과 PCF/RICF 동시 전송을 검증하는 테스트

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nncof.core import data_analyzer, decision_config
from nncof.core.data_analyzer import DataAnalyzer
from nncof.core.data_store import NotificationDataStore
from nncof.core.gnb2_rule_engine import Gnb2RuleEngine
from nncof.core.level_forecast import PeriodicForecaster
from nncof.core.subscription_request_builder import build_subscription_requests
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nupf.models.notification_data import NotificationData

_CLIENT_DIR = Path(__file__).resolve().parents[2] / "api-clients"
_UDUM_TEMPLATE = (
    Path(data_analyzer.__file__).parent / "12p_c_NotificationData_from_UPF_to_NCOF_v1.0.json"
)
_T0 = datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)

# 테스트용 UPF 샘플: correlationId → WLAN_DL_MBPS (가장 최근 값)
_METRICS: dict[str, float] = {}
# 같은 스트림의 직전·현재 샘플을 구별하기 위한 (correlationId, timeStamp) → WLAN_DL_MBPS
_METRICS_AT: dict[tuple[str, str], float] = {}
# 테스트 시계 — 기본은 "가장 최근에 넣은 샘플 시각"(= 신선한 샘플)
_NOW = [_T0]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(data_analyzer, "_shared_engine", None)
    monkeypatch.setattr(data_analyzer, "_active_analyzers", [])
    monkeypatch.setattr(data_analyzer, "_inflight_fanouts", set())
    monkeypatch.setattr(data_analyzer, "_retry_on_leader_tick", False)
    monkeypatch.setattr(data_analyzer, "_restoring", False)
    monkeypatch.setattr(data_analyzer, "_trend_refs", {})
    monkeypatch.setattr(data_analyzer, "_forecaster", PeriodicForecaster())
    monkeypatch.setattr(data_analyzer, "_retry_key", None)
    monkeypatch.setattr(data_analyzer, "_retry_armed_at", 0.0)
    monkeypatch.setattr(data_analyzer, "_last_join_at", -1e9)
    monkeypatch.setattr(decision_config, "_cache", decision_config.Gnb2DecisionConfig())
    monkeypatch.setattr(decision_config, "_cache_key", None)
    monkeypatch.setattr(decision_config, "_control_sequential_last", None)
    monkeypatch.setattr(decision_config, "_control_sequential_raw", None)
    for key in decision_config._KEYS + ("WLAN_SUB_REP_PERIOD_SEC", "GNB2_CONTROL_SEQUENTIAL"):
        monkeypatch.delenv(key, raising=False)
    conf = tmp_path / "ncof_setting.conf"
    conf.write_text("GNB2_TH_MBPS=500\n", encoding="utf-8")
    monkeypatch.setenv("NCOF_SETTING_FILE", str(conf))
    _METRICS.clear()
    _METRICS_AT.clear()
    _NOW[0] = _T0
    monkeypatch.setattr(data_analyzer, "_utcnow", lambda: _NOW[0])

    def fake_extract(d: dict) -> float:
        corr = d.get("correlationId") or d.get("correlation_id")
        items = d.get("notificationItems") or d.get("notification_items") or []
        ts = items[0].get("timeStamp") or items[0].get("time_stamp") if items else None
        key = (corr, ts.isoformat() if isinstance(ts, datetime) else str(ts))
        return _METRICS_AT.get(key, _METRICS[corr])

    monkeypatch.setattr(data_analyzer, "extract_wlan_dl_mbps", fake_extract)
    return conf


def _set_conf(conf: Path, text: str) -> None:
    conf.write_text(text, encoding="utf-8")
    st = conf.stat()
    os.utime(conf, (st.st_atime, st.st_mtime + 5))  # mtime 해상도와 무관하게 변경을 보장


def _analyzer(json_name: str, sent: list, result=True) -> DataAnalyzer:
    payload = json.loads((_CLIENT_DIR / json_name).read_text(encoding="utf-8"))
    analyzer: DataAnalyzer

    async def notify(nf_type: str, event: list[dict]):
        sent.append((analyzer.subscription_id, nf_type, event))
        return result

    analyzer = DataAnalyzer(
        subscription_id=f"sub-{json_name}",
        subscription=NncofEventsSubscription.from_dict(payload),
        notif_data_store=NotificationDataStore(),
        control_data_store=NotificationDataStore(),
        notify_callback=notify,
    )
    analyzer.is_running = True
    data_analyzer._active_analyzers.append(analyzer)
    return analyzer


def _recorder(analyzer: DataAnalyzer, sent: list, result: bool):
    """보낸 것을 sent 에 쌓고 result 를 돌려주는 가짜 전송 — 중간에 응답을 바꿀 때 쓴다."""

    async def notify(nf_type: str, event: list[dict]):
        sent.append((analyzer.subscription_id, nf_type, event))
        return result

    return notify


def _upf(analyzer: DataAnalyzer, corr_id: str, mbps: float, age_sec: int, wlan: bool) -> None:
    notif = NotificationData.from_dict(json.loads(_UDUM_TEMPLATE.read_text(encoding="utf-8")))
    notif.correlation_id = corr_id
    for item in notif.notification_items:
        item.time_stamp = _T0 + timedelta(seconds=age_sec)
    analyzer.notif_data_store.add_data("upf", corr_id, notif)
    _METRICS[corr_id] = mbps
    _METRICS_AT[(corr_id, (_T0 + timedelta(seconds=age_sec)).isoformat())] = mbps
    _NOW[0] = max(_NOW[0], _T0 + timedelta(seconds=age_sec))
    if wlan:
        analyzer.set_wlan_stream_ids(analyzer._wlan_stream_ids | {corr_id})


def _tick(analyzer: DataAnalyzer) -> None:
    asyncio.run(analyzer._analyze_and_generate(analyzer.get_source_nf_type()))


def _cell_state(event: list[dict]) -> str:
    info = event[0]["eventNotifications"][0]["_cellPowerCtrlOptInfos"][0]
    return info["_cellPowerCtrlInfos"][0]["_cellPowerParamSets"][0]["_cellPowerParamSet"][
        "_cellPowerState"
    ]


def _qos_sets(event: list[dict]) -> list[dict]:
    info = event[0]["eventNotifications"][0]["qosPolAssistInfos"][0]
    return info["qosPolAssistInfo"][0]["qosPolAssistSets"]


def _gbr_by_slot(event: list[dict]) -> list[tuple[str, str]]:
    """두두원 슬롯 순서(UE1 gNB1, UE2 WLAN client-1, UE3 gNB2, UE4 WLAN client-2)의 (gbrDl, mbrDl)."""
    return [(s["qosParamSet"]["gbrDl"], s["qosParamSet"]["mbrDl"]) for s in _qos_sets(event)]


def _nr_gnb2_off(event: list[dict]) -> bool:
    gnb2 = [
        s
        for s in _qos_sets(event)
        if any(g["gNbId"]["gNBValue"] == "000002" for g in s["spatialValidity"].get("gRanNodeIds", []) if "gNbId" in g)
    ]
    return [s["qosParamSet"]["gbrDl"] for s in gnb2] == ["0.0 Mbps"]


def _pair():
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    return sent, pcf, ricf


def test_leader_tick_sends_same_state_to_both():
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)

    _tick(pcf)  # pcf 가 먼저 시작 → 리더. 285 < 500 → DEEP_SLEEP

    by_nf = {nf: (sub, ev) for sub, nf, ev in sent}
    assert [nf for _, nf, _ in sent] == ["pcf", "ricf"]  # 끌 때는 14_e(0:100) 먼저
    assert _cell_state(by_nf["ricf"][1]) == "DEEP_SLEEP"
    assert _nr_gnb2_off(by_nf["pcf"][1])
    assert by_nf["pcf"][1][0]["subscriptionId"] == pcf.subscription_id
    assert by_nf["ricf"][1][0]["subscriptionId"] == ricf.subscription_id


def test_non_leader_tick_does_not_decide():
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _tick(pcf)
    sent.clear()

    _upf(ricf, "wlan-r", 900.0, 10, wlan=True)  # 더 새 샘플이 ACTIVE 값이어도
    _tick(ricf)  # 리더가 아니므로 판정하지 않는다

    assert sent == []
    assert pcf.decision_engine.last_emitted_state == "DEEP_SLEEP"
    _tick(pcf)  # 리더 틱에서 그 샘플로 판정 → 양쪽 ACTIVE
    assert sorted(nf for _, nf, _ in sent) == ["pcf", "ricf"]
    assert pcf.decision_engine.last_emitted_state == "ACTIVE"


def test_late_subscription_catches_up_on_its_own_tick():
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _tick(pcf)
    sent.clear()

    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _tick(ricf)  # 판정 없이 현재 상태만 받는다

    assert [(nf, _cell_state(ev)) for _, nf, ev in sent] == [("ricf", "DEEP_SLEEP")]


def test_input_is_wlan_stream_only_even_if_service_experience_is_newer():
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _upf(pcf, "se-p", 12458.99595, 30, wlan=False)  # 8_ 이상값이 더 늦게 왔다(9/30 19:54:33)

    _tick(pcf)

    assert pcf.decision_engine.last_emitted_state == "DEEP_SLEEP"


def test_newest_wlan_sample_across_subscriptions_is_used():
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _upf(ricf, "wlan-r", 600.0, 20, wlan=True)

    _tick(pcf)

    assert pcf.decision_engine.last_emitted_state == "ACTIVE"


def test_no_wlan_sample_yet_means_no_decision():
    sent, pcf, ricf = _pair()
    pcf.set_wlan_stream_ids({"wlan-p"})  # 12p_c 하위 구독은 있지만 아직 통지가 없다
    _upf(pcf, "se-p", 104.0, 0, wlan=False)

    _tick(pcf)

    assert sent == []
    assert pcf.decision_engine.last_emitted_state is None


def test_legacy_fallback_when_no_wlan_subscription_exists():
    sent, pcf, ricf = _pair()
    _upf(pcf, "any-p", 104.0, 0, wlan=False)

    _tick(pcf)

    assert pcf.decision_engine.last_emitted_state == "DEEP_SLEEP"


def test_threshold_and_hysteresis_are_read_from_setting_file(_isolate):
    conf = _isolate
    _set_conf(conf, "GNB2_TH_MBPS=287\nGNB2_HYST_MBPS=20\n")
    sent, pcf, ricf = _pair()

    for i, (mbps, expect) in enumerate(
        [(290.0, "ACTIVE"), (280.0, "ACTIVE"), (268.0, "ACTIVE"), (266.0, "DEEP_SLEEP"), (286.0, "DEEP_SLEEP"), (287.0, "ACTIVE")]
    ):
        _upf(pcf, "wlan-p", mbps, i * 60, wlan=True)
        _tick(pcf)
        assert pcf.decision_engine.last_emitted_state == expect, (mbps, expect)


def test_setting_change_applies_without_restart(_isolate, caplog):
    conf = _isolate
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 290.0, 0, wlan=True)
    _tick(pcf)
    assert pcf.decision_engine.last_emitted_state == "DEEP_SLEEP"  # TH 500
    sent.clear()

    _set_conf(conf, "GNB2_TH_MBPS=250\n")
    with caplog.at_level("WARNING"):
        _tick(pcf)

    assert pcf.decision_engine.last_emitted_state == "ACTIVE"
    assert sorted(nf for _, nf, _ in sent) == ["pcf", "ricf"]
    assert "판정 설정 변경: TH 500.0 → 250.0" in caplog.text


def test_invalid_setting_keeps_previous(_isolate):
    conf = _isolate
    _set_conf(conf, "GNB2_TH_MBPS=250\n")
    assert decision_config.current_decision_config().th_mbps == 250.0
    _set_conf(conf, "GNB2_TH_MBPS=abc\n")
    assert decision_config.current_decision_config().th_mbps == 250.0
    _set_conf(conf, "GNB2_TH_MBPS=250\nGNB2_HYST_MBPS=300\n")  # HYST >= TH
    assert decision_config.current_decision_config().hyst_mbps == 0.0


def test_setting_file_wins_over_exported_env(_isolate, monkeypatch):
    # run_http2.sh 가 설정 파일을 export 하므로 기동 시점 값이 환경변수로 남는다
    conf = _isolate
    monkeypatch.setenv("GNB2_TH_MBPS", "500")
    _set_conf(conf, "GNB2_TH_MBPS=250\n")
    assert decision_config.current_decision_config().th_mbps == 250.0


def test_failed_delivery_is_retried_from_the_start_on_next_tick():
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent, result=False)  # RICF 가 2xx 를 안 준다
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["pcf", "ricf"]
    # 성공한 14_e 도 「안 보냄」 으로 되돌린다 — 다음 틱에 처음부터(10/26 회신)
    assert ricf._delivered_state is None and pcf._delivered_state is None
    sent.clear()

    _tick(ricf)  # 리더가 아닌 틱은 다시 보내지 않는다 — 「다음 판정 주기」(리더 틱)에서
    assert sent == []

    _tick(pcf)  # 다음 판정 틱에서 처음부터 같은 순서로 다시 보낸다
    assert [nf for _, nf, _ in sent] == ["pcf", "ricf"]


def test_stopping_the_leader_mid_fanout_does_not_drop_other_delivery():
    sent: list = []
    release = asyncio.Event()

    async def run():
        pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
        ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
        _upf(pcf, "wlan-p", 285.0, 0, wlan=True)

        async def slow_ricf(nf_type, event):
            await release.wait()
            sent.append((ricf.subscription_id, nf_type, event))
            return True

        ricf._notify_callback = slow_ricf
        tick = asyncio.create_task(pcf._analyze_and_generate("PCF"))
        await asyncio.sleep(0.01)
        tick.cancel()  # 리더 구독이 전송 도중 stop() 된 상황
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(*list(data_analyzer._inflight_fanouts), return_exceptions=True)
        return ricf

    ricf = asyncio.run(run())
    assert "ricf" in [nf for _, nf, _ in sent]
    assert ricf._delivered_state == "DEEP_SLEEP"


# --- 순차 제어 (10/26 두두원 회신 · 10/27 두두원 답 — 14_e 는 UDP 송신 성공 시 200, 실패 시 500) ---


def test_on_transition_sends_15f_then_14e_and_off_sends_14e_then_15f(caplog):
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    with caplog.at_level("INFO"):
        _tick(pcf)  # 첫 판정이 ACTIVE(재기동 직후와 같다) — 목표 상태 규칙으로 15f 먼저
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]
    assert _cell_state(sent[0][2]) == "ACTIVE" and not _nr_gnb2_off(sent[1][2])
    assert "→ 구독 2건 순차 전송 (RICF:" in caplog.text
    assert "순차 제어 1/2 RICF 성공 응답 확인 → PCF" in caplog.text
    assert "순차 제어 2/2 PCF 성공 응답 확인 — 완료" in caplog.text
    sent.clear()

    _upf(pcf, "wlan-p", 285.0, 20, wlan=True)  # OFF — 트래픽(14_e 0:100) 먼저
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["pcf", "ricf"]
    assert _nr_gnb2_off(sent[0][2]) and _cell_state(sent[1][2]) == "DEEP_SLEEP"
    sent.clear()

    _upf(pcf, "wlan-p", 600.0, 40, wlan=True)  # 다시 ON
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]


def test_first_failure_stops_the_sequence_then_retries_from_the_start(caplog):
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _tick(pcf)  # DEEP_SLEEP 으로 시작
    sent.clear()

    ricf._notify_callback = _recorder(ricf, sent, False)  # 15f 가 500
    _upf(pcf, "wlan-p", 600.0, 20, wlan=True)  # ON
    with caplog.at_level("WARNING"):
        _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["ricf"]  # 15f 실패 → 14_e 는 보내지 않는다
    assert "순차 제어 1/2 RICF 실패 — PCF 는 보내지 않음, 다음 판정 틱에 처음부터 다시 보냄" in caplog.text
    assert ricf._delivered_state is None and pcf._delivered_state is None
    sent.clear()

    _tick(ricf)  # 리더가 아닌 틱은 곧바로 되풀이하지 않는다
    assert sent == []
    _tick(pcf)  # 다음 판정 틱 — 여전히 500 이면 또 15f 만
    assert [nf for _, nf, _ in sent] == ["ricf"]
    sent.clear()

    ricf._notify_callback = _recorder(ricf, sent, True)
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]
    assert ricf._delivered_state == pcf._delivered_state == "ACTIVE"
    sent.clear()
    _tick(pcf)
    assert sent == []  # 다 받았으면 더 안 보낸다


def test_next_request_waits_for_the_previous_response_and_other_ticks_do_not_interleave():
    sent: list = []
    events: list[str] = []
    release = asyncio.Event()

    async def run():
        pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
        ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
        _upf(pcf, "wlan-p", 600.0, 0, wlan=True)

        async def slow_ricf(nf_type, event):
            events.append("ricf 보냄")
            await release.wait()
            events.append("ricf 200")
            sent.append((ricf.subscription_id, nf_type, event))
            return True

        async def pcf_notify(nf_type, event):
            events.append("pcf 보냄")
            sent.append((pcf.subscription_id, nf_type, event))
            return True

        ricf._notify_callback = slow_ricf
        pcf._notify_callback = pcf_notify
        tick = asyncio.create_task(pcf._analyze_and_generate("PCF"))
        await asyncio.sleep(0.01)
        assert events == ["ricf 보냄"]  # 15f 응답 전 — 14_e 는 아직
        await ricf._analyze_and_generate("RICF")  # 응답을 기다리는 동안 다른 분석기의 틱
        assert events == ["ricf 보냄"]  # 끼어들어 따로 보내지 않는다
        release.set()
        await tick

    asyncio.run(run())
    assert events == ["ricf 보냄", "ricf 200", "pcf 보냄"]
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]


def _desc(sent: list) -> list[str]:
    return [
        f"ricf:{_cell_state(ev)}" if nf == "ricf" else ("pcf:OFF" if _nr_gnb2_off(ev) else "pcf:ON")
        for _, nf, ev in sent
    ]


def test_retry_after_failure_happens_once_per_decision_tick():
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent, result=False)  # 14_e 500 이 이어짐
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    for _ in range(3):  # 판정 주기 3번 = 리더 틱 3 + RICF 틱 3
        _tick(pcf)
        _tick(ricf)
    assert _desc(sent) == ["ricf:ACTIVE", "pcf:ON"] * 3  # 처음부터 · 판정 주기마다 한 번


def test_in_flight_sequence_is_not_interleaved_by_a_new_decision():
    """늦게 붙은 RICF 의 따라잡기(15f ACTIVE)가 응답을 기다리는 동안 리더가 DEEP_SLEEP 을 판정해도,
    14_e 0:100 은 그 15f 응답 뒤에 나간다(진행 중 fan-out 이 있으면 건너뜀)."""
    sent: list = []
    log: list[str] = []
    release = asyncio.Event()

    async def run():
        pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
        _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
        await pcf._analyze_and_generate("PCF")  # RICF 없이 ACTIVE — 14_e 만
        sent.clear()
        ricf = _analyzer("subscription_ricf_to_ncof.json", sent)

        async def slow_ricf(nf_type, event):
            log.append(f"ricf:{_cell_state(event)} 보냄")
            await release.wait()
            log.append(f"ricf:{_cell_state(event)} 200")
            sent.append((ricf.subscription_id, nf_type, event))
            return True

        async def pcf_notify(nf_type, event):
            log.append(("pcf:OFF" if _nr_gnb2_off(event) else "pcf:ON") + " 보냄")
            sent.append((pcf.subscription_id, nf_type, event))
            return True

        ricf._notify_callback = slow_ricf
        pcf._notify_callback = pcf_notify
        rtick = asyncio.create_task(ricf._analyze_and_generate("RICF"))  # 따라잡기 15f ACTIVE
        await asyncio.sleep(0.01)
        _upf(pcf, "wlan-p", 285.0, 20, wlan=True)
        await pcf._analyze_and_generate("PCF")  # DEEP_SLEEP 판정 — 진행 중이라 이번 틱은 건너뜀
        assert log == ["ricf:ACTIVE 보냄"]
        release.set()
        await rtick
        await pcf._analyze_and_generate("PCF")  # 다음 판정 틱에 OFF 쌍

    asyncio.run(run())
    assert log == ["ricf:ACTIVE 보냄", "ricf:ACTIVE 200", "pcf:OFF 보냄", "ricf:DEEP_SLEEP 보냄", "ricf:DEEP_SLEEP 200"]


def test_dead_duplicate_subscription_does_not_block_the_live_ones(caplog):
    """두두원만 재기동해 상향이 겹치면(고아 트리) 같은 NF 가 둘 — 죽은 하나가 살아 있는 구독의 제어를 막지 않는다."""
    sent: list = []
    dead = _analyzer("subscription_pcf_to_ncof.json", sent, result=False)  # 옛 상향(먼저 복원 → 목록 앞 · 리더)
    dead.subscription_id = "old-pcf-dead"
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    pcf.subscription_id = "new-pcf"
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    with caplog.at_level("WARNING"):
        _tick(dead)  # OFF: PCF 단계(죽은 것 실패 · 새 것 성공) → RICF 단계
    assert [(sub, nf) for sub, nf, _ in sent] == [
        ("old-pcf-dead", "pcf"),
        ("new-pcf", "pcf"),
        (ricf.subscription_id, "ricf"),
    ]
    assert "PCF 구독 2건(old-pcf-, new-pcf) — 같은 장비에 겹친 상향 구독(고아 트리)인지 확인" in caplog.text
    assert pcf._delivered_state == ricf._delivered_state == "DEEP_SLEEP" and dead._delivered_state is None
    sent.clear()
    _tick(dead)  # 죽은 것만 다시
    assert [sub for sub, _, _ in sent] == ["old-pcf-dead"]


def test_orphan_duplicate_ricf_does_not_block_split_only_14e(_isolate, caplog):
    """겹친 RICF 중 고아(실패)가 남아도, 다른 RICF 가 이미 ACTIVE 를 받았으면 단계만 바뀌는 14_e 는 나간다."""
    _level_conf(_isolate)
    sent: list = []
    orphan = _analyzer("subscription_ricf_to_ncof.json", sent, result=False)
    orphan.subscription_id = "old-ricf-orphan"
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 327.0, 0, wlan=True)  # 단계 2 ACTIVE
    _tick(orphan)  # 리더 = 목록 첫 활성(고아)
    assert [(sub, nf) for sub, nf, _ in sent] == [
        ("old-ricf-orphan", "ricf"),
        (ricf.subscription_id, "ricf"),
        (pcf.subscription_id, "pcf"),
    ]
    assert ricf._delivered_state == pcf._delivered_state == "ACTIVE" and orphan._delivered_state is None
    sent.clear()

    _upf(pcf, "wlan-p", 347.0, 20, wlan=True)  # 단계 3 — 상태는 그대로, split 만
    with caplog.at_level("WARNING"):
        _tick(orphan)
    assert [(sub, nf) for sub, nf, _ in sent] == [("old-ricf-orphan", "ricf"), (pcf.subscription_id, "pcf")]
    assert "순차 제어 1/2 RICF 겹친 구독만 실패 — 다른 RICF 구독이 이미 ACTIVE 를 받음 → PCF" in caplog.text
    assert _gbr_by_slot(sent[1][2]) == _lv(3)


def test_orphan_duplicate_retry_waits_for_the_leader_tick(_isolate):
    """겹친 구독 중 고아만 실패하고 단계를 넘긴 뒤에도 고아 재시도는 리더 판정 틱에서만 — 비리더 틱마다 되풀이하지 않는다
    (E2E v3: 500 고아 RICF 가 다른 구독 틱마다 판정 주기당 3번, 타임아웃 고아는 전송 슬롯을 거의 늘 차지)."""
    _level_conf(_isolate)
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)  # 리더
    orphan = _analyzer("subscription_ricf_to_ncof.json", sent, result=False)
    orphan.subscription_id = "old-ricf-orphan"
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 327.0, 0, wlan=True)  # 단계 2 ACTIVE
    _tick(pcf)
    assert [(sub, nf) for sub, nf, _ in sent] == [
        ("old-ricf-orphan", "ricf"),
        (ricf.subscription_id, "ricf"),
        (pcf.subscription_id, "pcf"),
    ]
    sent.clear()
    _tick(orphan)  # 비리더 틱 — 고아에 곧바로 다시 보내지 않는다
    _tick(ricf)
    assert sent == []
    _tick(pcf)  # 리더 틱 — 고아만 다시
    assert [sub for sub, _, _ in sent] == ["old-ricf-orphan"]
    sent.clear()
    _tick(orphan)  # 단계 통과(_held_by_peer) 뒤에도 비리더 틱은 그대로 건너뜀
    assert sent == []


def _join(json_name: str, sent: list, sub_id: str, result=True) -> DataAnalyzer:
    """운영 중 새로 들어온 상향 구독 — 실제 진입점 start() 로 fan-out 대상에 든다(주기 루프는 띄우지 않는다)."""
    a = _analyzer(json_name, sent, result)
    data_analyzer._active_analyzers.remove(a)
    a.subscription_id = sub_id
    a._periodic_process = lambda: asyncio.sleep(0)
    asyncio.run(a.start())
    return a


def test_app_restart_new_pcf_gets_14e_only_after_15f():
    """두두원 앱만 재기동(NCOF 그대로) — 옛 구독 2건이 고아로 남은 채 새 PCF 가 먼저 들어오면(새 RICF 는 4 ~ 6초 뒤)
    새 PCF 에 14_e 만 단독으로 나가면 안 된다(새 앱은 gNB2 OFF 로 초기화). 옛 RICF 로 15f 를 먼저 다시 보낸다."""
    sent, old_pcf, old_ricf = _pair()
    _upf(old_pcf, "wlan-p", 600.0, 0, wlan=True)
    _tick(old_pcf)  # ACTIVE — 옛 앱에 15f → 14_e
    sent.clear()

    new_pcf = _join("subscription_pcf_to_ncof.json", sent, "new-pcf")
    _tick(old_ricf)  # 리더가 아닌 틱도 「아직 못 받은 것」 을 보낸다 — 이때도 순서대로
    assert [(sub, nf) for sub, nf, _ in sent] == [
        (old_ricf.subscription_id, "ricf"),
        (old_pcf.subscription_id, "pcf"),
        ("new-pcf", "pcf"),
    ]
    assert _cell_state(sent[0][2]) == "ACTIVE"
    sent.clear()

    _join("subscription_ricf_to_ncof.json", sent, "new-ricf")
    _tick(old_pcf)
    assert [(sub, nf) for sub, nf, _ in sent] == [
        (old_ricf.subscription_id, "ricf"),
        ("new-ricf", "ricf"),
        (old_pcf.subscription_id, "pcf"),
        ("new-pcf", "pcf"),
    ]


def test_app_restart_orphan_ricf_rejected_holds_14e_until_new_ricf():
    """새 앱이 옛 subscriptionId 의 15f 를 거절하면(실패) 14_e 는 새 RICF 가 들어와 15f 200 을 받을 때까지 나가지 않는다."""
    sent, old_pcf, old_ricf = _pair()
    _upf(old_pcf, "wlan-p", 600.0, 0, wlan=True)
    _tick(old_pcf)
    sent.clear()

    old_ricf._notify_callback = _recorder(old_ricf, sent, False)
    _join("subscription_pcf_to_ncof.json", sent, "new-pcf")
    _tick(old_pcf)
    assert [nf for _, nf, _ in sent] == ["ricf"]  # 15f 실패 → 14_e 안 보냄
    sent.clear()

    _join("subscription_ricf_to_ncof.json", sent, "new-ricf")
    _tick(old_pcf)  # 리더 틱 — 처음부터: 옛 RICF 실패 · 새 RICF 200 → 14_e
    assert [(sub, nf) for sub, nf, _ in sent] == [
        (old_ricf.subscription_id, "ricf"),
        ("new-ricf", "ricf"),
        (old_pcf.subscription_id, "pcf"),
        ("new-pcf", "pcf"),
    ]


def test_app_restart_pending_split_retry_starts_from_15f(_isolate):
    """옛 앱이 죽은 뒤 단계만 바뀐 14_e 가 실패해 재시도를 기다리는 중 새 앱이 뜨면(gNB2 OFF), 새 PCF 구독이 붙기 전
    (하위 구독 · 화면 연출 약 4초) 리더 재시도가 옛 PCF 구독으로 14_e 만 새 앱에 보내면 안 된다 — 15f ACTIVE 부터."""
    _level_conf(_isolate)
    sent, old_pcf, old_ricf = _pair()
    _upf(old_pcf, "wlan-p", 327.0, 0, wlan=True)  # 단계 2 ACTIVE
    _tick(old_pcf)
    sent.clear()

    old_pcf._notify_callback = _recorder(old_pcf, sent, False)  # 옛 앱이 죽음
    old_ricf._notify_callback = _recorder(old_ricf, sent, False)
    _upf(old_pcf, "wlan-p", 347.0, 20, wlan=True)  # 죽기 전 마지막 샘플 — 단계 3
    _tick(old_pcf)
    assert [nf for _, nf, _ in sent] == ["pcf"]  # 단계만 바뀜 → 14_e 만, 실패
    sent.clear()

    old_pcf._notify_callback = _recorder(old_pcf, sent, True)  # 새 앱이 같은 포트로 뜸, 새 구독은 아직 안 붙음
    old_ricf._notify_callback = _recorder(old_ricf, sent, True)
    _tick(old_pcf)
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]
    assert _cell_state(sent[0][2]) == "ACTIVE" and _gbr_by_slot(sent[1][2]) == _lv(3)
    sent.clear()

    _join("subscription_pcf_to_ncof.json", sent, "new-pcf")
    _tick(old_ricf)
    assert [(sub, nf) for sub, nf, _ in sent] == [
        (old_ricf.subscription_id, "ricf"),
        (old_pcf.subscription_id, "pcf"),
        ("new-pcf", "pcf"),
    ]


def test_new_subscription_in_concurrent_mode_keeps_delivery_records(_isolate):
    """동시 모드(=0)는 예전 그대로 — 새 구독이 들어와도 남은 구독에 다시 보내지 않는다."""
    _set_conf(_isolate, "GNB2_TH_MBPS=500\nGNB2_CONTROL_SEQUENTIAL=0\n")
    sent, old_pcf, old_ricf = _pair()
    _upf(old_pcf, "wlan-p", 600.0, 0, wlan=True)
    _tick(old_pcf)
    sent.clear()

    _join("subscription_pcf_to_ncof.json", sent, "new-pcf")
    _tick(old_pcf)
    assert [(sub, nf) for sub, nf, _ in sent] == [("new-pcf", "pcf")]


def test_concurrent_mode_clears_the_leader_only_retry(_isolate):
    """순차 실패 뒤(리더 틱에서만 재시도) 동시 모드로 되돌리면 예전처럼 어느 틱이든 실패한 대상만 다시 보낸다."""
    sent, pcf, ricf = _pair()
    ricf._notify_callback = _recorder(ricf, sent, False)
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    _tick(pcf)  # 순차: 15f 실패 → 리더 틱에서만 재시도
    assert data_analyzer._retry_on_leader_tick is True
    sent.clear()
    _set_conf(_isolate, "GNB2_TH_MBPS=500\nGNB2_CONTROL_SEQUENTIAL=0\n")
    _tick(ricf)  # 비리더 틱 — 동시 모드면 막지 않는다
    assert sorted(nf for _, nf, _ in sent) == ["pcf", "ricf"]
    assert data_analyzer._retry_on_leader_tick is False


def test_target_stopped_mid_sequence_is_skipped():
    sent: list = []
    release = asyncio.Event()

    async def run():
        pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
        ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
        _upf(pcf, "wlan-p", 600.0, 0, wlan=True)

        async def slow_ricf(nf_type, event):
            await release.wait()
            sent.append((ricf.subscription_id, nf_type, event))
            return True

        ricf._notify_callback = slow_ricf
        tick = asyncio.create_task(pcf._analyze_and_generate("PCF"))
        await asyncio.sleep(0.01)
        pcf.is_running = False  # 15f 응답 대기 중 PCF 구독 삭제(handler.stop → analyzer.stop)
        pcf._leave_active_analyzers()
        tick.cancel()
        release.set()
        await asyncio.sleep(0)
        await asyncio.gather(*list(data_analyzer._inflight_fanouts), return_exceptions=True)

    asyncio.run(run())
    assert [nf for _, nf, _ in sent] == ["ricf"]  # 지워진 PCF 구독으로는 14_e 를 보내지 않는다


def test_hung_step_times_out_and_rolls_back(monkeypatch):
    monkeypatch.setattr(data_analyzer, "_STEP_TIMEOUT_SEC", 0.05)
    sent: list = []

    async def run():
        pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
        ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
        _upf(pcf, "wlan-p", 600.0, 0, wlan=True)

        async def hung(nf_type, event):
            await asyncio.Event().wait()

        ricf._notify_callback = hung
        await asyncio.wait_for(pcf._analyze_and_generate("PCF"), 1.0)
        return pcf, ricf

    pcf, ricf = asyncio.run(run())
    assert sent == []  # 15f 가 끝나지 않았으니 14_e 는 안 나감
    assert pcf._delivered_state is None and ricf._delivered_state is None
    assert not any(not f.done() for f in data_analyzer._inflight_fanouts)  # 다음 틱을 막지 않는다


def test_cancelled_sequence_rolls_back_every_target():
    sent: list = []

    async def run():
        pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
        ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
        _upf(pcf, "wlan-p", 600.0, 0, wlan=True)

        async def hung(nf_type, event):
            await asyncio.Event().wait()

        ricf._notify_callback = hung
        tick = asyncio.create_task(pcf._analyze_and_generate("PCF"))
        await asyncio.sleep(0.01)
        for f in list(data_analyzer._inflight_fanouts):
            f.cancel()  # 루프 종료 때의 취소
        await asyncio.gather(tick, return_exceptions=True)
        return pcf, ricf

    pcf, ricf = asyncio.run(run())
    assert pcf._delivered_state is None and ricf._delivered_state is None


def test_restoring_holds_control_until_every_saved_subscription_is_back():
    """상태파일 순서로 PCF 만 복원된 채 리더 틱이 ACTIVE 를 판정해도 14_e 단독으로 나가면 안 된다."""
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    data_analyzer.set_restoring(True)
    _tick(pcf)
    assert sent == []
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    data_analyzer.set_restoring(False)
    _tick(ricf)  # 복원이 끝난 뒤 어느 틱이든 — 처음부터 순서대로
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]
    assert _cell_state(sent[0][2]) == "ACTIVE"


def test_on_without_ricf_subscription_warns(caplog):
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    with caplog.at_level("WARNING"):
        _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["pcf"]
    assert "RICF 구독이 없어 15f ACTIVE 확인 없이 14_e 만 보낸다" in caplog.text


def test_sequential_off_by_setting_falls_back_to_concurrent_without_restart(_isolate, caplog):
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _tick(pcf)
    sent.clear()

    _set_conf(_isolate, "GNB2_TH_MBPS=500\nGNB2_CONTROL_SEQUENTIAL=0\n")
    ricf._notify_callback = _recorder(ricf, sent, False)
    _upf(pcf, "wlan-p", 600.0, 20, wlan=True)
    with caplog.at_level("INFO"):
        _tick(pcf)
    # 동시 — 15f 가 실패해도 14_e 는 나가고, 실패한 쪽만 다시 보낸다(예전 동작)
    assert sorted(nf for _, nf, _ in sent) == ["pcf", "ricf"]
    assert "→ 구독 2건 동시 전송" in caplog.text
    assert "제어 순서 설정 변경: 순차 → 동시 전송" in caplog.text
    assert pcf._delivered_state == "ACTIVE" and ricf._delivered_state is None
    sent.clear()
    _tick(ricf)
    assert [nf for _, nf, _ in sent] == ["ricf"]


def test_control_sequential_setting_values(_isolate, caplog):
    for text, expect in (("", True), ("1", True), ("on", True), ("0", False), ("OFF", False), ("false", False)):
        _set_conf(_isolate, f"GNB2_CONTROL_SEQUENTIAL={text}\n")
        assert decision_config.control_sequential() is expect, text
    with caplog.at_level("WARNING"):
        _set_conf(_isolate, "GNB2_CONTROL_SEQUENTIAL=maybe\n")
        assert decision_config.control_sequential() is True  # 잘못된 값 → 순차(기본)
        assert decision_config.control_sequential() is True
    assert caplog.text.count("GNB2_CONTROL_SEQUENTIAL 값 오류") == 1  # 같은 값으로 틱마다 반복하지 않는다


def test_downstream_requests_are_tagged_with_source_event():
    for name in ("subscription_pcf_to_ncof.json", "subscription_ricf_to_ncof.json"):
        payload = json.loads((_CLIENT_DIR / name).read_text(encoding="utf-8"))
        requests = build_subscription_requests("sub-x", NncofEventsSubscription.from_dict(payload))
        wlan = [r for r in requests if r.get("source_event") == "WLAN_PERFORMANCE"]
        assert [r["target"] for r in wlan] == ["smf"]
        assert wlan[0]["subscription"].notif_id
        assert all("source_event" in r for r in requests)


def test_stale_wlan_sample_holds_decision(caplog):
    # 두두원은 무트래픽이면 12p_c 를 안 보낸다 — 끊긴 스트림의 마지막 값으로 판정하지 않는다(10/1 실측 02:58:40 이후 끊김)
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 304.0, 0, wlan=True)
    _NOW[0] = _T0 + timedelta(seconds=3 * 20 + 1)  # 구독 repPeriod 20s × 3 초과
    with caplog.at_level("WARNING"):
        _tick(pcf)
    assert sent == [] and pcf.decision_engine.last_emitted_state is None
    assert "12p_c 끊김" in caplog.text

    _NOW[0] = _T0 + timedelta(seconds=3 * 20)  # 경계 안쪽이면 판정한다
    _tick(pcf)
    assert pcf.decision_engine.last_emitted_state == "DEEP_SLEEP"


def test_unreadable_setting_file_keeps_previous_config(_isolate):
    conf = _isolate
    _set_conf(conf, "GNB2_TH_MBPS=250\n")
    assert decision_config.current_decision_config().th_mbps == 250.0
    conf.write_bytes("# 한글 주석\nGNB2_TH_MBPS=300\n".encode("cp949"))  # CP949 로 저장된 파일
    st = conf.stat(); os.utime(conf, (st.st_atime, st.st_mtime + 10))
    assert decision_config.current_decision_config().th_mbps == 250.0
    _set_conf(conf, "GNB2_TH_MBPS=250\nGNB2_MIN_DWELL_SEC=inf\n")
    assert decision_config.current_decision_config().min_dwell_sec == 0


def test_removed_or_blank_key_falls_back_to_default_not_exported_env(_isolate, monkeypatch):
    conf = _isolate
    monkeypatch.setenv("GNB2_HYST_MBPS", "20")  # run_http2.sh 가 기동 때 export 한 값
    _set_conf(conf, "GNB2_TH_MBPS=287\nGNB2_HYST_MBPS=20\n")
    assert decision_config.current_decision_config().hyst_mbps == 20.0
    _set_conf(conf, "GNB2_TH_MBPS=287\n# GNB2_HYST_MBPS=20\n")
    assert decision_config.current_decision_config().hyst_mbps == 0.0
    _set_conf(conf, "GNB2_TH_MBPS=287\nGNB2_HYST_MBPS=\n")
    assert decision_config.current_decision_config().hyst_mbps == 0.0


def test_config_error_inside_leader_tick_does_not_raise(monkeypatch):
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)

    def boom():
        raise RuntimeError("config read failed")

    monkeypatch.setattr(data_analyzer, "current_decision_config", boom)
    _tick(pcf)  # 예외가 틱 밖으로 나가 판정 루프를 끝내면 안 된다
    assert sent == []


# --- trend 모드 (10/08): 임계 이상이면 지난 판정 때 본 값 대비 오르면 ACTIVE, 내리면 DEEP_SLEEP ---
# 12p_c 하위 구독은 10초, 판정 틱은 상향 repPeriod 20초 — 틱 사이에 샘플이 2개씩 쌓인다.


def _run_trend(pcf, ticks, stream="wlan-p", analyzer=None):
    """ticks: [([(시각 초, Mbps), ...], 기대 상태), ...] — 샘플들을 넣은 뒤 리더 틱을 한 번 돈다."""
    for samples, expect in ticks:
        for sec, mbps in samples:
            _upf(analyzer or pcf, stream, mbps, sec, wlan=True)
        _tick(pcf)
        assert pcf.decision_engine.last_emitted_state == expect, (samples, expect)


def _trend_conf(conf, extra=""):
    _set_conf(conf, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\n" + extra)


def test_trend_compares_with_value_seen_at_last_decision(_isolate):
    _trend_conf(_isolate)
    sent, pcf, ricf = _pair()
    _run_trend(
        pcf,
        [
            ([(0, 310.0), (10, 320.0)], "ACTIVE"),  # 첫 판정 — TH 기준
            ([(20, 360.0), (30, 350.0)], "ACTIVE"),  # 지난 판정 320 → 350 상승(10초 전 360 대비로는 하강)
            ([(40, 340.0), (50, 330.0)], "DEEP_SLEEP"),  # 350 → 330 하강, 아직 TH 이상
            ([(60, 340.0), (70, 345.0)], "ACTIVE"),  # 330 → 345 상승
            ([(80, 260.0), (90, 250.0)], "DEEP_SLEEP"),  # TH 미만
        ],
    )


def test_first_decision_is_threshold_even_if_two_samples_arrived(_isolate):
    # 재기동 직후 첫 틱 전에 12p_c 가 2개 온다(10초 하위·20초 틱) — 처음에는 TH 이상이면 그냥 ACTIVE
    _trend_conf(_isolate)
    sent, pcf, ricf = _pair()
    _run_trend(pcf, [([(0, 340.0), (10, 320.0)], "ACTIVE"), ([(20, 305.0), (30, 300.0)], "DEEP_SLEEP")])


def test_rise_between_ticks_is_not_lost(_isolate):
    # 바로 앞 10초 샘플과만 비교하면 280,280 | 360,360 의 상승(틱 사이 쌍)이 빠져 DEEP_SLEEP 에 갇혔다
    _trend_conf(_isolate, "GNB2_TREND_DEADBAND_MBPS=10\n")
    sent, pcf, ricf = _pair()
    _run_trend(
        pcf,
        [
            ([(0, 280.0), (10, 280.0)], "DEEP_SLEEP"),
            ([(20, 360.0), (30, 360.0)], "ACTIVE"),
            ([(40, 360.0), (50, 360.0)], "ACTIVE"),
        ],
    )


def test_crossing_threshold_from_below_is_active_even_within_deadband(_isolate):
    _trend_conf(_isolate, "GNB2_TREND_DEADBAND_MBPS=10\n")
    sent, pcf, ricf = _pair()
    _run_trend(
        pcf,
        [([(0, 250.0)], "DEEP_SLEEP"), ([(20, 295.0)], "DEEP_SLEEP"), ([(40, 303.0)], "ACTIVE")],
    )


def test_slow_ramp_accumulates_over_the_tick(_isolate):
    # 10초마다 +8 — 샘플 쌍으로는 데드밴드 10 을 못 넘지만 판정 틱(20초) 사이 +16 은 넘는다
    _trend_conf(_isolate, "GNB2_TREND_DEADBAND_MBPS=10\n")
    sent, pcf, ricf = _pair()
    _run_trend(
        pcf,
        [
            ([(0, 320.0), (10, 328.0)], "ACTIVE"),
            ([(20, 336.0), (30, 344.0)], "ACTIVE"),
            ([(40, 336.0), (50, 328.0)], "DEEP_SLEEP"),  # 344 → 328 = -16
            ([(60, 336.0), (70, 344.0)], "ACTIVE"),  # 328 → 344 = +16
        ],
    )


def test_flat_within_deadband_or_no_new_sample_keeps_state(_isolate):
    _trend_conf(_isolate, "GNB2_TREND_DEADBAND_MBPS=10\n")
    sent, pcf, ricf = _pair()
    _run_trend(
        pcf,
        [
            ([(0, 330.0)], "ACTIVE"),
            ([(20, 315.0)], "DEEP_SLEEP"),  # -15
            ([(40, 322.0)], "DEEP_SLEEP"),  # +7 ≤ 10 → 유지
            ([], "DEEP_SLEEP"),  # 새 샘플 없음(같은 샘플) → Δ 0 → 유지
            ([(60, 340.0)], "ACTIVE"),  # 322 → 340 = +18
        ],
    )


def test_trend_reference_is_per_stream(_isolate):
    # 최신 샘플이 RICF 트리 스트림으로 바뀌어도 그 스트림의 지난 판정 값과 비교한다
    _trend_conf(_isolate)
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 330.0, 0, wlan=True)
    _upf(ricf, "wlan-r", 400.0, 1, wlan=True)
    _tick(pcf)  # 최신 = wlan-r 400 → 첫 판정 ACTIVE. 기준: wlan-p 330, wlan-r 400
    assert pcf.decision_engine.last_emitted_state == "ACTIVE"
    _upf(ricf, "wlan-r", 360.0, 20, wlan=True)
    _upf(pcf, "wlan-p", 350.0, 21, wlan=True)  # 최신 = wlan-p 350 — 기준은 wlan-p 330(상승), wlan-r 400 이 아니다
    _tick(pcf)
    assert pcf.decision_engine.last_emitted_state == "ACTIVE"


def test_reference_older_than_allowance_is_ignored(_isolate):
    # 끊긴 뒤 첫 판정은 '처음' 과 같다 — 허용 나이(상향 repPeriod 20 × 3 = 60초)보다 먼 기준과 비교하지 않는다
    _trend_conf(_isolate)
    sent, pcf, ricf = _pair()
    _run_trend(pcf, [([(0, 330.0)], "ACTIVE"), ([(20, 320.0)], "DEEP_SLEEP")])
    _run_trend(pcf, [([(81, 310.0)], "ACTIVE")])  # 기준 320@20 과 61초 — 기준 없음 → TH 이상 ACTIVE


def test_engine_reset_clears_trend_reference(_isolate):
    _trend_conf(_isolate)
    sent, pcf, ricf = _pair()
    _run_trend(pcf, [([(0, 330.0)], "ACTIVE")])
    assert data_analyzer._trend_refs
    for a in (pcf, ricf):
        a._leave_active_analyzers()
    assert data_analyzer._trend_refs == {}


def test_trend_mode_is_read_without_restart_and_threshold_is_default(_isolate, caplog):
    sent, pcf, ricf = _pair()
    _set_conf(_isolate, "GNB2_TH_MBPS=300\n")
    _run_trend(pcf, [([(0, 320.0)], "ACTIVE"), ([(20, 310.0)], "ACTIVE")])  # threshold — 하강해도 TH 이상이면 ACTIVE
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=TREND\n")
    with caplog.at_level("WARNING"):
        _run_trend(pcf, [([(40, 305.0)], "DEEP_SLEEP")])  # 기준 310(threshold 때도 남겨 둔다) → 하강
    assert "MODE threshold → trend" in caplog.text


def test_invalid_trend_settings_keep_previous(_isolate):
    conf = _isolate
    _set_conf(conf, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\nGNB2_TREND_DEADBAND_MBPS=5\n")
    assert decision_config.current_decision_config().mode == "trend"
    _set_conf(conf, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=slope\nGNB2_TREND_DEADBAND_MBPS=5\n")
    assert decision_config.current_decision_config().mode == "trend"
    _set_conf(conf, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\nGNB2_TREND_DEADBAND_MBPS=-1\n")
    assert decision_config.current_decision_config().trend_deadband_mbps == 5.0


def _wlan_and_other_periods(name: str):
    payload = json.loads((_CLIENT_DIR / name).read_text(encoding="utf-8"))
    sub = NncofEventsSubscription.from_dict(payload)
    requests = build_subscription_requests("sub-x", sub)
    wlan = [r["subscription"].to_dict() for r in requests if r.get("source_event") == "WLAN_PERFORMANCE"]
    other = [r["subscription"].to_dict() for r in requests if r.get("source_event") != "WLAN_PERFORMANCE"]
    return sub.evt_req.rep_period, wlan, other


def _periods(body: dict) -> set:
    """하위 본문에서 두두원 Get_Ncof_Rep_Period 가 읽는 자리들의 repPeriod."""
    found = set()
    if body.get("repPeriod") is not None:
        found.add(body["repPeriod"])
    if (body.get("eventsRepInfo") or {}).get("repPeriod") is not None:
        found.add(body["eventsRepInfo"]["repPeriod"])
    for s in body.get("eventsSubs") or []:
        if (s.get("eventRepInfo") or {}).get("repPeriod") is not None:
            found.add(s["eventRepInfo"]["repPeriod"])
    return found


def test_wlan_sub_rep_period_overrides_only_wlan_stream(_isolate):
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nWLAN_SUB_REP_PERIOD_SEC=10\n")
    for name in ("subscription_pcf_to_ncof.json", "subscription_ricf_to_ncof.json"):
        upstream, wlan, other = _wlan_and_other_periods(name)
        assert [_periods(b) for b in wlan] == [{10}]
        assert other and all(_periods(b) <= {upstream} for b in other), name


def test_wlan_sub_rep_period_unset_or_invalid_follows_upstream(_isolate):
    for text in ("GNB2_TH_MBPS=300\n", "WLAN_SUB_REP_PERIOD_SEC=\n", "WLAN_SUB_REP_PERIOD_SEC=0\n", "WLAN_SUB_REP_PERIOD_SEC=ten\n"):
        _set_conf(_isolate, text)
        upstream, wlan, other = _wlan_and_other_periods("subscription_pcf_to_ncof.json")
        assert [_periods(b) for b in wlan] == [{upstream}], text


# --- level 모드 (10/19): 12p_c 를 경계로 단계에 넣고, 단계별 몫으로 쌍마다 gNB set + WLAN set 합(1000)을 나눈다 ---
# 노트북2 쌍(gNB2 + WLAN client-2) = gNB2 몫, 노트북1 쌍(gNB1 + WLAN client-1) = gNB1 몫(아래 「gNB1 쌍」 절).
# 두두원 UPF 는 set 3(gNB2) 과 set 4(WLAN client-2) 의 mbr 비만 10% 단위로 쓴다(CUPB_SbiComm.c:96-97).
# 기본 경계 172/305/338 Mbps · gNB2 몫 0/50/70/90% — 10/17 ~ 10/19 실측 틱 값(≈151, 327, 347 · 최고 ≈370)의 빈 구간.

from nncof.core.decide_wlan_gnb2_rule import apply_qos_policy, level_index, split_for_pct

_QOS_TEMPLATE = Path(data_analyzer.__file__).parent / "14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json"
_UNTOUCHED = ("5.0 Mbps", "10.0 Mbps")  # 템플릿 값 — gNB1 set 은 threshold/trend(와 gNB1 쌍 끔)에서 그대로


def _slots(gnb2: float, wlan: float, gnb1: float | None = None, wlan1: float | None = None) -> list[tuple[str, str]]:
    """두두원 슬롯 순서 [gNB1, WLAN client-1, gNB2, WLAN client-2] 의 (gbrDl, mbrDl). gnb1 이 없으면 gNB1 그대로 · WLAN 미러."""
    def v(x: float) -> tuple[str, str]:
        return (f"{float(x)} Mbps",) * 2

    first = _UNTOUCHED if gnb1 is None else v(gnb1)
    return [first, v(wlan if wlan1 is None else wlan1), v(gnb2), v(wlan)]


_GNB2_PCT = (0, 50, 70, 90)  # 기본 몫 — 노트북2 쌍(gNB2 + WLAN client-2)
_GNB1_PCT = (30, 50, 70, 90)  # 기본 몫 — 노트북1 쌍(gNB1 + WLAN client-1), 사용자 표 300:700 / 500:500 / 700:300 / 900:100


def _lv(level: int) -> list[tuple[str, str]]:
    """기본 설정(총 1000)에서 단계 level 의 4 슬롯 값."""
    g2, g1 = 10 * _GNB2_PCT[level], 10 * _GNB1_PCT[level]
    return _slots(g2, 1000 - g2, g1, 1000 - g1)


def _level_conf(conf, extra=""):
    _set_conf(conf, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=level\n" + extra)


def _tick_sends(pcf, sec, mbps):
    """샘플 하나를 넣고 리더 틱을 돈 뒤 이번 틱에 나간 [(nf, 이벤트)]."""
    sent_before = len(pcf._sent)
    _upf(pcf, "wlan-p", mbps, sec, wlan=True)
    _tick(pcf)
    return [(nf, ev) for _, nf, ev in pcf._sent[sent_before:]]


def _level_pair():
    sent, pcf, ricf = _pair()
    pcf._sent = sent
    return sent, pcf, ricf


def test_level_index_and_split_are_pure_and_grid_aligned():
    bounds = (172.0, 305.0, 338.0)
    assert [level_index(x, bounds) for x in (123.0, 171.9, 172.0, 304.9, 305.0, 337.9, 338.0, 375.0)] == [
        0, 0, 1, 1, 2, 2, 3, 3,
    ]
    assert [split_for_pct(p, 1000) for p in (0, 50, 70, 90)] == [(0, 1000), (500, 500), (700, 300), (900, 100)]
    for p in range(0, 101, 10):  # UPF: (int)(g*100/(g+w)) 가 몫 그대로 나와야 10% 격자에 1:1
        g, w = split_for_pct(p, 1000)
        assert g + w == 1000 and int(g * 100 / (g + w)) == p


def test_apply_qos_policy_split_fills_gnb2_and_both_wlan_sets_only():
    template = json.loads(_QOS_TEMPLATE.read_text(encoding="utf-8"))
    iso = "2026-10-19T20:00:00+09:00"

    active = apply_qos_policy(template, "ACTIVE", iso, "sub", "corr", (700, 300))
    assert _gbr_by_slot(active) == _slots(700, 300)

    # DEEP_SLEEP 이면 split 과 상관없이 gNB2 0 · WLAN 합계 — 셀이 꺼진 쪽으로 몫을 주지 않는다
    asleep = apply_qos_policy(template, "DEEP_SLEEP", iso, "sub", "corr", (500, 500))
    assert _gbr_by_slot(asleep) == _slots(0, 1000)

    # split 없이 부르면 예전 상수 그대로(trend/threshold 모드 회귀 없음)
    assert _gbr_by_slot(apply_qos_policy(template, "ACTIVE", iso, "sub", "corr")) == _slots(1000, 500)
    assert _gbr_by_slot(apply_qos_policy(template, "DEEP_SLEEP", iso, "sub", "corr")) == _slots(0, 1000)
    assert template[0]["eventNotifications"][0]["qosPolAssistInfos"][0]["qosPolAssistInfo"][0][
        "qosPolAssistSets"
    ][2]["qosParamSet"]["gbrDl"] == "5.0 Mbps"  # 템플릿 원본은 건드리지 않는다


def test_level_cycle_sends_pcf_on_split_change_and_ricf_on_state_change(_isolate, caplog):
    _level_conf(_isolate)
    sent, pcf, ricf = _level_pair()

    with caplog.at_level("INFO"):
        out = _tick_sends(pcf, 0, 151.0)  # 단계 0
    assert sorted(nf for nf, _ in out) == ["pcf", "ricf"]
    by_nf = dict(out)
    assert _cell_state(by_nf["ricf"]) == "DEEP_SLEEP" and _gbr_by_slot(by_nf["pcf"]) == _lv(0)
    assert _nr_gnb2_off(by_nf["pcf"])
    assert (
        "단계 판정: WLAN 151.0 Mbps → 단계 0 DEEP_SLEEP (gNB2:WLAN 0:1000 Mbps · gNB1:WLAN 300:700 Mbps, 경계 172/305/338)"
        in caplog.text
    )

    out = _tick_sends(pcf, 20, 327.0)  # 단계 2 — 상태도 바뀜
    by_nf = dict(out)
    assert sorted(by_nf) == ["pcf", "ricf"]
    assert _cell_state(by_nf["ricf"]) == "ACTIVE" and _gbr_by_slot(by_nf["pcf"]) == _lv(2)

    out = _tick_sends(pcf, 40, 347.0)  # 단계 3 — 상태는 같고 split 만 바뀜 → PCF 만
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _lv(3)

    assert _tick_sends(pcf, 60, 370.0) == []  # 같은 단계 → 안 보냄

    out = _tick_sends(pcf, 80, 185.0)  # 최고(370)의 절반 → 50:50
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _lv(1)

    caplog.clear()  # 아래 로그 단언이 첫 틱(같은 문구)이 아니라 이 틱을 보게
    out = _tick_sends(pcf, 100, 151.0)
    assert sorted(nf for nf, _ in out) == ["pcf", "ricf"]
    assert _gbr_by_slot(dict(out)["pcf"]) == _lv(0)
    assert "AI 분석 결과: gNB2 DEEP_SLEEP · gNB2:WLAN 0:1000 Mbps · gNB1:WLAN 300:700 Mbps → 구독 2건" in caplog.text


def test_level_mode_ignores_threshold_and_trend(_isolate):
    # TH 300 · trend 였다면 200 은 DEEP_SLEEP, 360 → 340 하강도 DEEP_SLEEP 이다
    _level_conf(_isolate, "GNB2_TREND_DEADBAND_MBPS=10\nGNB2_HYST_MBPS=50\n")
    sent, pcf, ricf = _level_pair()
    for sec, mbps, state, level in [(0, 200.0, "ACTIVE", 1), (20, 360.0, "ACTIVE", 3), (40, 340.0, "ACTIVE", 3), (60, 171.0, "DEEP_SLEEP", 0)]:
        _upf(pcf, "wlan-p", mbps, sec, wlan=True)
        _tick(pcf)
        engine = pcf.decision_engine
        assert (engine.last_emitted_state, engine.last_emitted_level) == (state, level), mbps


def test_switching_trend_to_level_resends_pcf_once_without_ricf(_isolate):
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\n")
    sent, pcf, ricf = _level_pair()
    out = _tick_sends(pcf, 0, 320.0)
    assert _gbr_by_slot(dict(out)["pcf"]) == _slots(1000, 500)  # trend — 예전 상수
    assert pcf.decision_engine.last_emitted_split is None

    _level_conf(_isolate)
    out = _tick_sends(pcf, 20, 320.0)  # 상태는 ACTIVE 그대로, split 이 생김 → PCF 만 한 번
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _lv(2)
    assert _tick_sends(pcf, 40, 321.0) == []

    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\n")  # 되돌리기 — 재기동 없이
    out = _tick_sends(pcf, 60, 330.0)  # trend: 321 → 330 상승 ACTIVE, split 없음 → PCF 만 예전 상수로
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _slots(1000, 500)
    assert pcf.decision_engine.last_emitted_gnb1_split is None  # level 때 gNB1 split 이 trend 로 새지 않는다


def test_failed_pcf_split_delivery_is_retried(_isolate):
    _level_conf(_isolate)
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent, result=False)  # PCF 가 2xx 를 안 준다
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent)
    _upf(pcf, "wlan-p", 327.0, 0, wlan=True)
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]  # 켤 때는 15f 먼저
    assert pcf._delivered_state is None and pcf._delivered_split is None
    assert ricf._delivered_state is None  # 15f 는 성공했어도 처음부터 다시 보내도록 되돌린다
    sent.clear()

    _tick(pcf)  # 같은 샘플 — 처음부터 15f → 14_e
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"] and _gbr_by_slot(sent[1][2]) == _lv(2)

    # 상태는 그대로 ACTIVE 이고 split 만 바뀌면 14_e 만 — 실패해도 14_e 만 다시
    sent.clear()
    pcf._notify_callback = _recorder(pcf, sent, True)
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"]  # 위 실패 때문에 아직 둘 다 못 받음 → 처음부터
    sent.clear()
    _upf(pcf, "wlan-p", 347.0, 20, wlan=True)  # 단계 3
    pcf._notify_callback = _recorder(pcf, sent, False)
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["pcf"]
    # 하나도 성공 못 함 — 두두원 앱 재기동일 수 있어 묶음 밖 RICF 기록도 지운다 → 다시 보낼 때는 15f ACTIVE 부터
    assert ricf._delivered_state is None
    sent.clear()
    pcf._notify_callback = _recorder(pcf, sent, True)
    _tick(pcf)
    assert [nf for _, nf, _ in sent] == ["ricf", "pcf"] and _gbr_by_slot(sent[1][2]) == _lv(3)


def test_dwell_never_breaks_deep_sleep_means_gnb2_zero(_isolate):
    _level_conf(_isolate, "GNB2_MIN_DWELL_SEC=3600\n")
    sent, pcf, ricf = _level_pair()
    out = _tick_sends(pcf, 0, 151.0)
    assert _gbr_by_slot(dict(out)["pcf"]) == _lv(0)
    assert _tick_sends(pcf, 20, 360.0) == []  # dwell 이 DEEP_SLEEP 을 붙잡는 동안 gNB2 몫도 0 그대로

    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=level\n")
    out = _tick_sends(pcf, 40, 360.0)
    assert _gbr_by_slot(dict(out)["pcf"]) == _lv(3)
    _level_conf(_isolate, "GNB2_MIN_DWELL_SEC=3600\n")
    out = _tick_sends(pcf, 60, 151.0)  # dwell 이 ACTIVE 를 붙잡으면 ACTIVE 중 가장 낮은 단계(50:50)
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _lv(1)
    assert pcf.decision_engine.last_emitted_state == "ACTIVE"


def test_level_settings_are_hot_reloaded_and_validated(_isolate, caplog):
    conf = _isolate
    g1 = "GNB2_LEVEL_GNB1_PCT=30,60,80\n"  # 경계가 둘이면 gNB1 몫도 셋
    _level_conf(conf, "GNB2_LEVEL_BOUNDS_MBPS=150, 300\nGNB2_LEVEL_GNB2_PCT=0,60,80\nGNB2_SPLIT_TOTAL_MBPS=500\n" + g1)
    cfg = decision_config.current_decision_config()
    assert (cfg.mode, cfg.level_bounds_mbps, cfg.level_gnb2_pct, cfg.level_gnb1_pct, cfg.split_total_mbps) == (
        "level", (150.0, 300.0), (0, 60, 80), (30, 60, 80), 500,
    )
    good = cfg
    with caplog.at_level("WARNING"):
        for bad in (
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=10,60,80\n",  # 단계 0 은 0 이어야
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60\n",  # 개수
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,55,80\n",  # 10% 격자
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,80,60\n",  # 감소
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,0,60\n",  # 단계 1 이상은 >0
            "GNB2_LEVEL_BOUNDS_MBPS=300,150\nGNB2_LEVEL_GNB2_PCT=0,60,80\n",  # 경계 순서
            "GNB2_LEVEL_BOUNDS_MBPS=150,150\nGNB2_LEVEL_GNB2_PCT=0,60,80\n",  # 같은 경계
            "GNB2_LEVEL_BOUNDS_MBPS=150,abc\nGNB2_LEVEL_GNB2_PCT=0,60,80\n",  # 숫자 아님
            "GNB2_LEVEL_BOUNDS_MBPS=150,,300\nGNB2_LEVEL_GNB2_PCT=0,60,70,80\n",  # 빈 칸
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,80\nGNB2_SPLIT_TOTAL_MBPS=1001\n",  # 600.6 Mbps
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,80\nGNB2_SPLIT_TOTAL_MBPS=0\n",
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,80\nGNB2_SPLIT_TOTAL_MBPS=100100\n",  # 상한
            "GNB2_LEVEL_BOUNDS_MBPS=150,inf\nGNB2_LEVEL_GNB2_PCT=0,60,80\n",
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,110\n",  # 0~100
            "GNB2_LEVEL_BOUNDS_MBPS=0,300\nGNB2_LEVEL_GNB2_PCT=0,60,80\n",  # 경계 > 0
            "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,80\nGNB2_SPLIT_TOTAL_MBPS=1000.5\n",  # 정수
        ):
            _level_conf(conf, bad + g1)
            assert decision_config.current_decision_config() == good, bad
    assert "판정 설정 단계 오류" in caplog.text
    assert "숫자가 아님: GNB2_LEVEL_BOUNDS_MBPS='150,abc'" in caplog.text  # 어느 키인지 남긴다

    caplog.clear()
    with caplog.at_level("WARNING"):
        _level_conf(conf, "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,10,100\n" + g1)
        assert decision_config.current_decision_config().level_gnb2_pct == (0, 10, 100)  # 허용하되 경고
    assert "gNB2 몫 [10, 100]%" in caplog.text
    assert (
        "LEVEL 경계 150/300 Mbps · gNB2 0/60/80% · gNB1 30/60/80% · 총 500 Mbps → "
        "경계 150/300 Mbps · gNB2 0/10/100% · gNB1 30/60/80% · 총 1000 Mbps" in caplog.text
    )


def test_level_keys_absent_means_recommended_defaults_and_trend_unaffected(_isolate):
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\n")
    cfg = decision_config.current_decision_config()
    assert (cfg.level_bounds_mbps, cfg.level_gnb2_pct, cfg.split_total_mbps) == ((172.0, 305.0, 338.0), (0, 50, 70, 90), 1000)
    sent, pcf, ricf = _level_pair()
    _tick_sends(pcf, 0, 151.0)
    assert pcf.decision_engine.last_emitted_level is None and pcf.decision_engine.last_emitted_split is None


def test_custom_level_settings_reach_engine_and_14e(_isolate):
    # 경계·몫·총합을 핫리로드로 바꾸면 판정과 14_e 값이 그대로 따라간다(엔진 기본값과 같은 기본 설정만으로는 안 드러난다)
    g1 = "GNB2_LEVEL_GNB1_PCT=20,40,80\n"
    _level_conf(_isolate, "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,80\nGNB2_SPLIT_TOTAL_MBPS=500\n" + g1)
    sent, pcf, ricf = _level_pair()
    out = dict(_tick_sends(pcf, 0, 160.0))  # 기본 경계(172)였다면 DEEP_SLEEP
    assert _cell_state(out["ricf"]) == "ACTIVE" and _gbr_by_slot(out["pcf"]) == _slots(300, 200, 200, 300)
    out = _tick_sends(pcf, 20, 320.0)
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _slots(400, 100, 400, 100)

    _level_conf(_isolate, "GNB2_LEVEL_BOUNDS_MBPS=150,300\nGNB2_LEVEL_GNB2_PCT=0,60,70\nGNB2_SPLIT_TOTAL_MBPS=500\n" + g1)
    out = _tick_sends(pcf, 40, 320.0)  # 같은 단계, 몫만 바뀜 → PCF 만 다시
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _slots(350, 150, 400, 100)


def test_bad_level_keys_do_not_block_other_modes(_isolate, caplog):
    conf = _isolate
    _level_conf(conf)
    assert decision_config.current_decision_config().mode == "level"
    with caplog.at_level("WARNING"):
        # level 운용 중 몫을 잘못 저장한 뒤 trend 로 되돌린다 — 롤백은 받아들여야 한다
        _set_conf(conf, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\nGNB2_LEVEL_GNB2_PCT=0,50,70,95\n")
        cfg = decision_config.current_decision_config()
        assert (cfg.mode, cfg.th_mbps, cfg.level_gnb2_pct) == ("trend", 300.0, (0, 50, 70, 90))
        # trend 에서 쓰지 않는 level 키가 잘못돼 있어도 TH 변경은 반영된다
        _set_conf(conf, "GNB2_TH_MBPS=250\nGNB2_DECISION_MODE=trend\nGNB2_LEVEL_BOUNDS_MBPS=172,,338\n")
        cfg = decision_config.current_decision_config()
        assert (cfg.mode, cfg.th_mbps, cfg.level_bounds_mbps) == ("trend", 250.0, (172.0, 305.0, 338.0))
        # 그 상태로 level 로 바꾸려 하면 거부(직전 trend 유지)
        _set_conf(conf, "GNB2_TH_MBPS=250\nGNB2_DECISION_MODE=level\nGNB2_LEVEL_BOUNDS_MBPS=172,,338\n")
        assert decision_config.current_decision_config().mode == "trend"
    assert "level 모드가 아니라 단계 값만 직전 값" in caplog.text


def test_restart_with_bad_level_keys_keeps_trend_settings(_isolate):
    # 재기동(직전 설정 = 코드 기본값)이어도 level 키 오류 때문에 threshold·TH 500 으로 떨어지지 않는다
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_MODE=trend\nGNB2_LEVEL_GNB2_PCT=0,55,70,90\n")
    cfg = decision_config.current_decision_config()
    assert (cfg.mode, cfg.th_mbps, cfg.level_gnb2_pct) == ("trend", 300.0, (0, 50, 70, 90))


# --- level 모드 gNB1 쌍 (10/19 저녁): 노트북1 쌍(gNB1 set + WLAN client-1 set)도 같은 단계로 나눈다 ---
# 사용자 표: 단계 0 300:700 · 1 500:500 · 2 700:300 · 3 900:100 (gNB1:WLAN). gNB1 은 잠들지 않는다.
# ⚠️ 두두원 UPF(CUPB_SbiComm.c)는 지금 TN/NTN 한 쌍만 적용해 정상(…102 · …104 세션 있음)이면 노트북1 쌍 값은 UPF 에
# 반영되지 않는다 — NCOF 는 그대로 보낸다.


def test_gnb1_pair_matches_user_table_at_every_level(_isolate):
    _level_conf(_isolate)
    sent, pcf, ricf = _level_pair()
    for sec, mbps, level, gnb1 in [(0, 151.0, 0, 300), (20, 200.0, 1, 500), (40, 327.0, 2, 700), (60, 347.0, 3, 900)]:
        out = dict(_tick_sends(pcf, sec, mbps))
        slots = _gbr_by_slot(out["pcf"])
        assert pcf.decision_engine.last_emitted_level == level
        assert slots[0] == (f"{float(gnb1)} Mbps",) * 2 and slots[1] == (f"{float(1000 - gnb1)} Mbps",) * 2, mbps
        assert slots == _lv(level)
    assert pcf.decision_engine.last_emitted_gnb1_split == (900, 100)


def test_gnb1_share_change_alone_resends_pcf_only(_isolate):
    _level_conf(_isolate)
    sent, pcf, ricf = _level_pair()
    _tick_sends(pcf, 0, 327.0)
    _level_conf(_isolate, "GNB2_LEVEL_GNB1_PCT=30,50,60,90\n")
    out = _tick_sends(pcf, 20, 327.0)  # 단계 · gNB2 몫 그대로, gNB1 몫만 바뀜
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _slots(700, 300, 600, 400)
    assert _tick_sends(pcf, 40, 327.0) == []


def test_wlan_sets_pair_by_app_id_not_by_order():
    template = json.loads(_QOS_TEMPLATE.read_text(encoding="utf-8"))
    sets = template[0]["eventNotifications"][0]["qosPolAssistInfos"][0]["qosPolAssistInfo"][0]["qosPolAssistSets"]
    sets[:] = [sets[3], sets[2], sets[1], sets[0]]  # [WLAN client-2, gNB2, WLAN client-1, gNB1]
    out = apply_qos_policy(template, "ACTIVE", "2026-10-19T21:00:00+09:00", "sub", "corr", (700, 300), (300, 700))
    got = {(s["appId"].rsplit("/", 1)[-1], s["ratTypes"][0]): s["qosParamSet"]["gbrDl"] for s in _qos_sets(out)}
    assert got == {
        ("client-2", "WLAN"): "300.0 Mbps",
        ("client-2", "NR"): "700.0 Mbps",
        ("client-1", "WLAN"): "700.0 Mbps",
        ("client-1", "NR"): "300.0 Mbps",
    }


def test_gnb1_share_validation(_isolate, caplog):
    conf = _isolate
    _level_conf(conf, "GNB2_LEVEL_GNB1_PCT=0,50,70,90\n")  # gNB1 은 단계 0 에 0 이어도 된다
    good = decision_config.current_decision_config()
    assert good.level_gnb1_pct == (0, 50, 70, 90)
    with caplog.at_level("WARNING"):
        for bad in ("30,50,70", "30,55,70,90", "30,50,90,70", "30,50,70,abc", "30,50,70,110"):
            _level_conf(conf, f"GNB2_LEVEL_GNB1_PCT={bad}\n")
            assert decision_config.current_decision_config() == good, bad
        # trend 모드에서는 gNB1 몫 오류가 TH 변경을 막지 않는다(단계 값만 직전 값)
        _set_conf(conf, "GNB2_TH_MBPS=250\nGNB2_DECISION_MODE=trend\nGNB2_LEVEL_GNB1_PCT=30,50,70\n")
        cfg = decision_config.current_decision_config()
        assert (cfg.mode, cfg.th_mbps, cfg.level_gnb1_pct) == ("trend", 250.0, (0, 50, 70, 90))
    assert "gNB1 몫 개수 = 경계 개수 + 1" in caplog.text and "gNB1 몫은 비감소" in caplog.text


def test_gnb1_key_absent_with_other_bound_count_turns_gnb1_pair_off(_isolate, caplog):
    # e8267db 에서 유효하던 conf(경계 2개 · GNB1 키 없음)를 새 코드로 재기동해도 level 이 그대로 뜬다 —
    # 기본 gNB1 몫(4개)이 안 맞는다고 설정 전체를 거부하면 직전 설정 = 코드 기본값(threshold · TH 500)으로 떨어진다
    off = "GNB2_LEVEL_BOUNDS_MBPS=200,300\nGNB2_LEVEL_GNB2_PCT=0,50,90\n"
    with caplog.at_level("WARNING"):
        _level_conf(_isolate, off)
        cfg = decision_config.current_decision_config()
    assert (cfg.mode, cfg.th_mbps, cfg.level_bounds_mbps, cfg.level_gnb2_pct, cfg.level_gnb1_pct) == (
        "level", 300.0, (200.0, 300.0), (0, 50, 90), (),
    )
    assert "GNB2_LEVEL_GNB1_PCT 가 없고 기본 gNB1 몫(30/50/70/90%)을 이 설정에 쓸 수 없다(gNB1 몫 개수 = 경계 개수 + 1)" in caplog.text
    assert "판정 설정 단계 오류" not in caplog.text

    sent, pcf, ricf = _level_pair()
    out = dict(_tick_sends(pcf, 0, 250.0))  # 단계 1 — gNB1 쌍 끔: gNB1 set 그대로 · WLAN set 둘 다 노트북2 몫(e8267db 동작)
    assert pcf.decision_engine.last_emitted_gnb1_split is None
    assert _gbr_by_slot(out["pcf"]) == _slots(500, 500)

    # 끔 → 켬: 단계 · 상태 · gNB2 split 은 그대로이고 gNB1 쪽만 None 에서 값으로 → PCF 만 한 번
    _level_conf(_isolate, off + "GNB2_LEVEL_GNB1_PCT=30,50,90\n")
    out = _tick_sends(pcf, 20, 250.0)
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _slots(500, 500, 500, 500)
    assert _tick_sends(pcf, 40, 250.0) == []

    # 켬 → 끔: 값에서 None 으로 → PCF 만 한 번, gNB1 set 은 템플릿 값 · WLAN 미러로 돌아간다
    _level_conf(_isolate, off)
    out = _tick_sends(pcf, 60, 250.0)
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _slots(500, 500)
    assert _tick_sends(pcf, 80, 250.0) == []

    # 경계 개수가 기본값과 맞으면 키가 없어도 기본 몫(사용자 표)을 쓴다
    _level_conf(_isolate)
    assert decision_config.current_decision_config().level_gnb1_pct == _GNB1_PCT
    out = _tick_sends(pcf, 100, 327.0)
    assert [nf for nf, _ in out] == ["pcf"] and _gbr_by_slot(out[0][1]) == _lv(2)


def test_gnb1_key_absent_with_more_bounds_turns_gnb1_pair_off(_isolate, caplog):
    # 경계가 기본(3개)보다 많은 쪽도 같다 — 기본 gNB1 몫 4개 < 경계+1
    with caplog.at_level("INFO"):
        _level_conf(_isolate, "GNB2_LEVEL_BOUNDS_MBPS=150,250,300,350\nGNB2_LEVEL_GNB2_PCT=0,50,60,70,90\n")
        cfg = decision_config.current_decision_config()
    assert (cfg.mode, cfg.level_bounds_mbps, cfg.level_gnb2_pct, cfg.level_gnb1_pct) == (
        "level", (150.0, 250.0, 300.0, 350.0), (0, 50, 60, 70, 90), (),
    )
    assert "판정 설정 단계 오류" not in caplog.text
    assert "gNB2 0/50/60/70/90% · gNB1 끔 · 총 1000 Mbps" in caplog.text  # 기동 로그의 「판정 설정」 줄
    sent, pcf, ricf = _level_pair()
    out = dict(_tick_sends(pcf, 0, 320.0))  # 단계 3 — gNB2 70%
    assert pcf.decision_engine.last_emitted_gnb1_split is None and _gbr_by_slot(out["pcf"]) == _slots(700, 300)


def test_gnb1_key_absent_with_total_off_grid_turns_gnb1_pair_off(_isolate, caplog):
    # 개수가 맞아도 기본 gNB1 몫(30 · 70%)이 총합과 안 맞으면(505 × 30 / 100 이 정수가 아님) 같은 이유로 끈다 —
    # e8267db 에서 유효하던 conf 가 사용자가 적지도 않은 gNB1 값 때문에 거부되면 안 된다
    total505 = "GNB2_LEVEL_GNB2_PCT=0,20,40,60\nGNB2_SPLIT_TOTAL_MBPS=505\n"
    with caplog.at_level("WARNING"):
        _level_conf(_isolate, total505)
        cfg = decision_config.current_decision_config()
    assert (cfg.mode, cfg.th_mbps, cfg.level_gnb2_pct, cfg.level_gnb1_pct, cfg.split_total_mbps) == (
        "level", 300.0, (0, 20, 40, 60), (), 505,
    )
    assert "기본 gNB1 몫(30/50/70/90%)을 이 설정에 쓸 수 없다(총합×gNB1 몫/100 이 정수)" in caplog.text
    assert "판정 설정 단계 오류" not in caplog.text

    # 키를 적었으면 같은 나눗셈 오류는 거부한다(직전 설정 유지) — 사용자가 고칠 값이다
    caplog.clear()
    with caplog.at_level("WARNING"):
        _level_conf(_isolate, total505 + "GNB2_LEVEL_GNB1_PCT=30,50,70,90\n")
        assert decision_config.current_decision_config() == cfg
    assert "판정 설정 단계 오류(총합×gNB1 몫/100 이 정수)" in caplog.text


def test_gnb1_share_validation_edges(_isolate, caplog):
    conf = _isolate
    for ok in ("30,30,70,90", "0,0,50,90"):  # 비감소는 같은 값 허용 · gNB1 은 어느 단계든 0 이어도 된다
        _level_conf(conf, f"GNB2_LEVEL_GNB1_PCT={ok}\n")
        assert decision_config.current_decision_config().level_gnb1_pct == tuple(int(v) for v in ok.split(",")), ok
    # inf/nan 은 단계 오류로만 다룬다 — trend 의 TH 변경은 막지 않는다(직전 = level · TH 300)
    for th, bad in ((250, "30,50,70,inf"), (260, "nan,50,70,90")):
        _set_conf(conf, f"GNB2_TH_MBPS={th}\nGNB2_DECISION_MODE=trend\nGNB2_LEVEL_GNB1_PCT={bad}\n")
        cfg = decision_config.current_decision_config()
        assert (cfg.mode, cfg.th_mbps, cfg.level_gnb1_pct) == ("trend", float(th), (0, 0, 50, 90)), bad
    caplog.clear()
    with caplog.at_level("WARNING"):
        _level_conf(conf, "GNB2_LEVEL_GNB1_PCT=10,50,70,100\n")
        assert decision_config.current_decision_config().level_gnb1_pct == (10, 50, 70, 100)  # 허용하되 경고
    assert "gNB1 몫 [10, 100]%" in caplog.text


def test_gnb1_share_from_env_when_setting_file_absent(_isolate, monkeypatch):
    # 설정 파일이 없으면 환경변수를 본다 — gNB1 몫 환경변수가 바뀌면(캐시 키) 다시 읽는다
    _isolate.unlink()
    monkeypatch.setenv("GNB2_TH_MBPS", "300")
    monkeypatch.setenv("GNB2_DECISION_MODE", "level")
    monkeypatch.setenv("GNB2_LEVEL_GNB1_PCT", "20,50,70,90")
    assert decision_config.current_decision_config().level_gnb1_pct == (20, 50, 70, 90)
    monkeypatch.setenv("GNB2_LEVEL_GNB1_PCT", "40,50,70,90")
    assert decision_config.current_decision_config().level_gnb1_pct == (40, 50, 70, 90)



# --- level 선제 판정 (11/04 칠판 시나리오): 오를 때 한 주기 전 12p_c 로 미리, 내릴 때 샘플 확인 뒤 ---
# bg 70(120초) → 200(40) → 300(40) → 400(40) → 530(60) → 300(40) 을 340초마다. 경계 150/250/350/450 · gNB2 0/30/50/100/100.
_SCENARIO = [(70, 120), (200, 40), (300, 40), (400, 40), (530, 60), (300, 40)]
_SCN_BOUNDS = (150.0, 250.0, 350.0, 450.0)
_SCN_CONF = (
    "GNB2_LEVEL_BOUNDS_MBPS=150,250,350,450\nGNB2_LEVEL_GNB2_PCT=0,30,50,100,100\n"
    "GNB2_LEVEL_GNB1_PCT=50,50,50,50,50\nGNB2_DECISION_TICK_SEC=2\nGNB2_PREDICT_PERIOD_SEC=340\n"
    "GNB2_PREDICT_LEAD_SEC=18\nGNB2_PREDICT_MATCH_MBPS=30\nGNB2_DOWN_CONFIRM_SAMPLES=2\n"
    "WLAN_SUB_REP_PERIOD_SEC=10\n"  # 12p_c 평균 창 — 없으면 상향 repPeriod(테스트 구독 20초)로 본다
)


def _bg(t: float, period: float = 340.0) -> float:
    u = t % period
    for rate, dur in _SCENARIO:
        if u < dur:
            return rate
        u -= dur
    return _SCENARIO[0][0]


def _w10(ts: float, period: float = 340.0) -> float:
    """두두원 12p_c — 최근 10초 udptp 평균."""
    return sum(_bg(ts - 10 + k + 0.5, period) for k in range(10)) / 10


def _history(until: float, period: float = 340.0, phase: float = 3.0) -> PeriodicForecaster:
    fc = PeriodicForecaster()
    ts = phase + 10
    while ts <= until:
        fc.add("wlan", _T0 + timedelta(seconds=ts), _w10(ts, period))
        ts += 10
    return fc


def test_forecaster_sees_next_rise_one_period_ahead():
    # 세 번째 주기의 70 → 200 계단(800초) — 한 주기 전 이력으로 18초 앞을 본다(일치 확인은 한 주기 반쯤 쌓인 뒤부터)
    fc = _history(800 - 15)
    soon = fc.forecast(_T0 + timedelta(seconds=800 - 15), 340, 18, 10, 30)
    assert soon.reason == "ok" and soon.peak_mbps >= 150
    early = fc.forecast(_T0 + timedelta(seconds=800 - 30), 340, 18, 10, 30)
    assert early.reason == "ok" and early.peak_mbps < 150
    assert _history(460 - 15).forecast(_T0 + timedelta(seconds=460 - 15), 340, 18, 10, 30).reason.startswith("이력 부족")


def test_forecaster_needs_a_period_and_a_matching_pattern():
    fc = _history(200)
    assert fc.forecast(_T0 + timedelta(seconds=200), 340, 18, 10, 30).peak_mbps is None  # 한 주기도 안 됨
    other = _history(900, period=380)  # 실제 주기 380 인데 340 으로 내다보면 끈다
    out = other.forecast(_T0 + timedelta(seconds=900), 340, 18, 10, 30)
    assert out.peak_mbps is None and out.reason.startswith("패턴 불일치")


def test_forecaster_turns_off_at_the_first_mismatched_step():
    # 세 번째 주기 70 → 200(800초)이 오지 않고 70 그대로(bg 송신기 재기동 · 위상 바뀜) — 한 주기 평균은 아직 괜찮지만 최근 창이 끈다
    fc = _history(800)
    for ts in (813, 823, 833):
        fc.add("wlan", _T0 + timedelta(seconds=ts), 70.0)
    out = fc.forecast(_T0 + timedelta(seconds=835), 340, 18, 10, 30)
    assert out.peak_mbps is None and out.reason.startswith("최근 어긋남"), out
    assert out.match_err_mbps <= 30


def _scn_engine(confirm: int = 2) -> Gnb2RuleEngine:
    engine = Gnb2RuleEngine()
    engine.apply_config(
        decision_config.Gnb2DecisionConfig(
            mode="level",
            level_bounds_mbps=_SCN_BOUNDS,
            level_gnb2_pct=(0, 30, 50, 100, 100),
            level_gnb1_pct=(50,) * 5,
            down_confirm_samples=confirm,
        )
    )
    return engine


def test_level_down_waits_for_confirmation_and_skips_intermediate_level():
    engine = _scn_engine()
    iso = "2026-11-04T15:00:00+09:00"
    engine.update_state(300.0, iso, recent_mbps=[300.0, 300.0])
    assert engine.last_emitted_level == 2
    # 300 → 70 계단을 걸친 평균 185 (단계 1) — 곧바로 3:7 로 내리지 않는다
    engine.update_state(185.0, iso, recent_mbps=[300.0, 185.0])
    assert (engine.last_emitted_level, engine.last_emitted_state) == (2, "ACTIVE")
    assert engine.last_level_note.startswith("내림 대기")
    engine.update_state(70.0, iso, recent_mbps=[185.0, 70.0])
    assert engine.last_emitted_level == 2  # 아직 한 개
    engine.update_state(70.0, iso, recent_mbps=[70.0, 70.0])
    assert (engine.last_emitted_level, engine.last_emitted_state) == (0, "DEEP_SLEEP")  # 5:5 → DEEP_SLEEP 바로
    assert engine.last_emitted_split == (0, 1000)


def test_level_rise_is_immediate_and_forecast_raises_early_and_holds():
    engine = _scn_engine()
    iso = "2026-11-04T15:00:00+09:00"
    engine.update_state(70.0, iso, recent_mbps=[70.0, 70.0])
    assert engine.last_emitted_state == "DEEP_SLEEP"
    engine.update_state(70.0, iso, recent_mbps=[70.0, 70.0], forecast_mbps=205.0)  # 18초 안에 200 이 온다
    assert (engine.last_emitted_level, engine.last_emitted_state) == (1, "ACTIVE")
    assert engine.last_emitted_split == (300, 700) and engine.last_level_note.startswith("선제")
    engine.update_state(70.0, iso, recent_mbps=[70.0, 70.0], forecast_mbps=205.0)  # 아직 70 이어도 예측대로 유지
    assert engine.last_emitted_level == 1 and engine.last_level_note.startswith("선제 유지")
    engine.update_state(320.0, iso, recent_mbps=[70.0, 320.0])  # 오를 때는 확인 없이 곧바로
    assert engine.last_emitted_level == 2


def test_recent_counts_one_sample_per_window_across_streams():
    fc = PeriodicForecaster()
    for stream, off in (("a", 0.0), ("b", 0.3)):  # 같은 위상의 두 스트림
        for ts, v in ((90, 300.0), (100, 212.0), (110, 100.0)):
            fc.add(stream, _T0 + timedelta(seconds=ts + off), v)
    assert fc.recent(2) == [100.0, 100.0]  # 창으로 거르지 않으면 같은 창 두 개
    assert fc.recent(2, 8.0) == [212.0, 100.0]
    assert fc.recent(3, 8.0) == [300.0, 212.0, 100.0]


def test_two_wlan_streams_do_not_confirm_a_drop_from_one_window(_isolate):
    """PCF · RICF 쌍마다 WLAN 하위 구독이 있어 같은 창의 12p_c 가 두 번 온다 — 300 → 100 내림에서 3:7 을 거치면 안 된다."""
    _level_conf(_isolate, _SCN_CONF)
    sent, pcf, ricf = _level_pair()
    seen = []
    for ts, v in ((10, 300.0), (20, 300.0), (30, 212.0), (40, 100.0), (50, 100.0)):
        _upf(pcf, "wlan-p", v, ts, wlan=True)
        _upf(ricf, "wlan-r", v, ts, wlan=True)  # 같은 timeStamp 근처(여기선 같은 초)
        _NOW[0] = _T0 + timedelta(seconds=ts + 1)
        _tick(pcf)
        seen.append(pcf.decision_engine.last_emitted_level)
    assert seen == [2, 2, 2, 2, 0], seen


def test_down_confirm_one_or_no_history_is_the_old_behaviour():
    for engine, recent in ((_scn_engine(confirm=1), [300.0, 185.0]), (_scn_engine(confirm=2), None)):
        iso = "2026-11-04T15:00:00+09:00"
        engine.update_state(300.0, iso, recent_mbps=recent)
        engine.update_state(185.0, iso, recent_mbps=recent)
        assert engine.last_emitted_level == 1


def test_timing_keys_are_parsed_and_bad_ones_keep_only_themselves(_isolate, caplog):
    _level_conf(_isolate, _SCN_CONF)
    cfg = decision_config.current_decision_config()
    assert (cfg.decision_tick_sec, cfg.predict_period_sec, cfg.predict_lead_sec) == (2, 340, 18)
    assert (cfg.predict_match_mbps, cfg.down_confirm_samples, cfg.level_gnb2_pct) == (30.0, 2, (0, 30, 50, 100, 100))
    with caplog.at_level("WARNING"):
        _level_conf(_isolate, _SCN_CONF.replace("GNB2_PREDICT_LEAD_SEC=18", "GNB2_PREDICT_LEAD_SEC=400")
                    .replace("GNB2_LEVEL_BOUNDS_MBPS=150,250,350,450", "GNB2_LEVEL_BOUNDS_MBPS=160,250,350,450"))
        cfg = decision_config.current_decision_config()
    assert "판정 틱 · 선제 설정 범위 오류" in caplog.text
    assert cfg.predict_lead_sec == 18 and cfg.predict_period_sec == 340  # 이 값들만 직전 그대로
    assert cfg.level_bounds_mbps[0] == 160.0  # 다른 변경은 들어간다


def _run_scenario(pcf, until: float, tick: float = 2.0, phase: float = 3.0, delay: float = 1.2):
    """12p_c 를 10초마다(timeStamp 뒤 delay 초에 도착) 넣으며 tick 초마다 리더 틱 — [(시각, 단계, 상태)] 변화만."""
    changes = []
    next_ts = phase + 10
    t = 0.0
    engine = pcf.decision_engine
    while t <= until:
        while next_ts + delay <= t:
            _upf(pcf, "wlan-p", _w10(next_ts), next_ts, wlan=True)
            next_ts += 10
        _NOW[0] = _T0 + timedelta(seconds=t)
        before = (engine.last_emitted_level, engine.last_emitted_state)
        _tick(pcf)
        after = (engine.last_emitted_level, engine.last_emitted_state)
        if after != before:
            changes.append((t, *after))
        t += tick
    return changes


def test_leader_raises_10_to_20_s_before_each_rise_and_drops_after(_isolate):
    _level_conf(_isolate, _SCN_CONF)
    sent, pcf, ricf = _level_pair()
    changes = _run_scenario(pcf, 3 * 340 + 40)
    third = 2 * 340  # 세 번째 주기 — 앞 주기 이력과 일치 확인이 끝난 뒤

    def first_at(level, lo, hi):
        return next(t for t, lv, _ in changes if lv == level and lo <= t <= hi)

    for step, level in ((120, 1), (160, 2), (200, 3)):  # 70→200 · 200→300 · 300→400(10:0)
        lead = third + step - first_at(level, third + step - 40, third + step + 30)
        assert 10 <= lead <= 20, (step, level, lead, changes)
    # 530 → 300(300초) · 300 → 70(340초): 계단 뒤에, 중간 단계 없이
    down = [(t - third, lv) for t, lv, _ in changes if third + 300 <= t <= third + 340 + 40]
    assert [lv for _, lv in down] == [2, 0] and all(dt > 300 for dt, _ in down[:1]) and down[1][0] > 340
    assert ("ACTIVE", "DEEP_SLEEP") == (changes[-2][2], changes[-1][2]) or changes[-1][2] == "DEEP_SLEEP"


def test_short_tick_retries_the_same_failed_delivery_once_per_rep_period(_isolate, monkeypatch):
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_TICK_SEC=2\n")
    clock = [1000.0]
    monkeypatch.setattr(data_analyzer.time, "monotonic", lambda: clock[0])
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent, result=False)
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    _tick(pcf)
    assert _desc(sent) == ["ricf:ACTIVE"]  # ON: 15f 실패 → 14_e 안 보냄
    sent.clear()
    for _ in range(5):  # 2초 틱 — 같은 묶음은 상향 repPeriod(20) - 틱(2) = 18초 안에 다시 안 보낸다
        clock[0] += 2
        _tick(pcf)
    assert sent == []
    clock[0] += 10  # 실패 뒤 20초
    _tick(pcf)
    assert _desc(sent) == ["ricf:ACTIVE"]
    sent.clear()
    clock[0] += 2
    _upf(pcf, "wlan-p", 100.0, 10, wlan=True)  # 새 판정(DEEP_SLEEP)은 기다리지 않는다
    _tick(pcf)
    assert _desc(sent)[:1] == ["pcf:OFF"]


def test_short_tick_waits_for_the_pair_before_the_first_control(_isolate, monkeypatch):
    """11/04 17:10 실장비 — 빈 NCOF 에 새 앱이 PCF → (4초) → RICF 순으로 구독, 분석기는 각각 약 6초 뒤에 붙는다.
    2초 틱이 첫 12p_c 에 바로 판정해 RICF 가 붙기 전에 14_e(ON)만 나갔다. 마지막 합류 뒤 _JOIN_GRACE_SEC 는 보류."""
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_TICK_SEC=2\n")
    clock = [1000.0]
    monkeypatch.setattr(data_analyzer.time, "monotonic", lambda: clock[0])
    sent: list = []
    pcf = _join("subscription_pcf_to_ncof.json", sent, "new-pcf")
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    clock[0] += 4
    _tick(pcf)
    assert sent == [] and pcf.decision_engine.last_emitted_state == "ACTIVE"  # 판정은 하되 보내지 않는다
    _join("subscription_ricf_to_ncof.json", sent, "new-ricf")
    clock[0] += 10
    _tick(pcf)
    assert sent == []  # RICF 합류 뒤 아직 15초 안
    clock[0] += 6
    _tick(pcf)
    assert _desc(sent) == ["ricf:ACTIVE", "pcf:ON"]


def test_short_tick_resend_after_records_cleared_is_not_backed_off(_isolate, monkeypatch):
    """전송 중 새 구독이 붙어 전달 기록이 지워진 것은 실패가 아니다 — 같은 묶음 재시도 간격(repPeriod - 틱)을 걸지 않는다."""
    _set_conf(_isolate, "GNB2_TH_MBPS=300\nGNB2_DECISION_TICK_SEC=2\n")
    clock = [1000.0]
    monkeypatch.setattr(data_analyzer.time, "monotonic", lambda: clock[0])
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    _analyzer("subscription_ricf_to_ncof.json", sent)
    cleared = [False]

    async def notify(nf_type, event):
        sent.append((pcf.subscription_id, nf_type, event))
        if not cleared[0]:  # 14_e 를 보내는 사이 새 상향 구독이 붙었다(_join_active_analyzers 가 기록을 지움)
            cleared[0] = True
            data_analyzer._clear_delivery_records()
        return True

    pcf._notify_callback = notify
    _upf(pcf, "wlan-p", 600.0, 0, wlan=True)
    _tick(pcf)
    assert _desc(sent) == ["ricf:ACTIVE", "pcf:ON"]
    sent.clear()
    clock[0] += 2
    _tick(pcf)
    assert _desc(sent) == ["ricf:ACTIVE", "pcf:ON"]  # 다음 틱에 곧바로 처음부터
