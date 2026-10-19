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
    monkeypatch.setattr(data_analyzer, "_trend_refs", {})
    monkeypatch.setattr(decision_config, "_cache", decision_config.Gnb2DecisionConfig())
    monkeypatch.setattr(decision_config, "_cache_key", None)
    for key in decision_config._KEYS + ("WLAN_SUB_REP_PERIOD_SEC",):
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


def test_leader_tick_sends_same_state_to_both_at_once():
    sent, pcf, ricf = _pair()
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)

    _tick(pcf)  # pcf 가 먼저 시작 → 리더. 285 < 500 → DEEP_SLEEP

    by_nf = {nf: (sub, ev) for sub, nf, ev in sent}
    assert set(by_nf) == {"pcf", "ricf"}
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


def test_failed_delivery_is_retried_on_next_tick():
    sent: list = []
    pcf = _analyzer("subscription_pcf_to_ncof.json", sent)
    ricf = _analyzer("subscription_ricf_to_ncof.json", sent, result=False)  # RICF 가 2xx 를 안 준다
    _upf(pcf, "wlan-p", 285.0, 0, wlan=True)
    _tick(pcf)
    assert ricf._delivered_state is None and pcf._delivered_state == "DEEP_SLEEP"
    sent.clear()

    _tick(ricf)  # 자기 틱에서 다시 보낸다

    assert [nf for _, nf, _ in sent] == ["ricf"]


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
    assert pcf._delivered_state is None and pcf._delivered_split is None
    assert ricf._delivered_state == "ACTIVE"
    sent.clear()

    _tick(pcf)  # 같은 샘플 — PCF 만 다시
    assert [nf for _, nf, _ in sent] == ["pcf"] and _gbr_by_slot(sent[0][2]) == _lv(2)


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
