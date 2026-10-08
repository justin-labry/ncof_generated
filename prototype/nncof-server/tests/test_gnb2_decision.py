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


def _nr_gnb2_off(event: list[dict]) -> bool:
    info = event[0]["eventNotifications"][0]["qosPolAssistInfos"][0]
    return "0.0 Mbps" in [s["qosParamSet"]["gbrDl"] for s in info["qosPolAssistInfo"][0]["qosPolAssistSets"]]


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
