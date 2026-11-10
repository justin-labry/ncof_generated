# gNB2 판정 설정(임계·히스테리시스·최소 유지)을 ncof_setting.conf 에서 읽는다

import logging
import math
import os
from dataclasses import dataclass

from dotenv import dotenv_values

from .nrf import _find_upwards

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Gnb2DecisionConfig:
    """룰 엔진 판정 설정.

    - th_mbps: 12p_c WLAN DL 이 이 값 이상이면 ACTIVE, 미만이면 DEEP_SLEEP
    - hyst_mbps: ACTIVE 에서 DEEP_SLEEP 으로는 th_mbps - hyst_mbps 미만일 때만 내려간다(0 = 끔)
    - min_dwell_sec: 상태가 바뀐 뒤 최소 유지 시간(0 = 끔)
    - mode: "threshold"(위 임계 규칙만) | "trend"(임계 이상일 때 같은 12p_c 스트림을 지난 판정 때 본 값 대비
      오르면 ACTIVE, 내리면 DEEP_SLEEP) | "level"(아래 경계로 단계를 정하고, 단계 0 이면 DEEP_SLEEP · 그 위는 ACTIVE.
      th·hyst·deadband 는 쓰지 않는다)
    - trend_deadband_mbps: trend 에서 |현재 - 지난 판정 값| 이 이 값 이하면 "변화 없음"으로 보고 현재 상태를 유지한다
    - level_bounds_mbps: level 단계 경계(오름차순). 첫 값 미만이 단계 0(DEEP_SLEEP)
    - level_gnb2_pct: 단계별 gNB2 몫(%) — 개수는 경계+1, 첫 값은 0, 나머지는 10 의 배수(비감소)
    - level_gnb1_pct: 단계별 gNB1(노트북1 쌍 — gNB1 set + WLAN client-1 set) 몫(%) — 개수는 경계+1, 10 의 배수(비감소).
      gNB1 은 잠들지 않으므로 단계 0 에도 0 이 아니어도 된다. 빈 값 = gNB1 쌍 분배 끔(키가 없고 기본값이 경계 개수나
      총합과 안 맞을 때)
    - split_total_mbps: 쌍(노트북1 · 노트북2)마다 gNB set + WLAN set 의 gbr/mbr 합. 두두원 UPF 는 지금 노트북2 쌍
      (gNB2 set · 노트북2 WLAN set)의 mbr 비만 10% 단위로 쓴다
    - decision_tick_sec: 판정 틱(초). 0 = 상향 repPeriod(예전 그대로). 그보다 짧으면 그 간격으로 판정한다(모든 모드)
    - predict_period_sec: level 모드 선제 판정 — bg 가 되풀이되는 주기(초). 0 = 끔(사후 판정만)
    - predict_lead_sec: 선제 판정이 내다보는 시간(초) — 이 안에 단계가 오를 것으로 보이면 지금 올린다
    - predict_match_mbps: 최근 한 주기 샘플이 그 앞 주기와 이 값(평균 오차) 안으로 맞을 때만 예측을 쓴다
    - down_confirm_samples: level 모드에서 단계를 내릴 때 최근 12p_c 샘플이 이 개수만큼 모두 같은 낮은 단계여야
      내린다(1 = 곧바로 — 예전 그대로). 오를 때는 곧바로(지금 값이나 예측)
    """

    th_mbps: float = 500.0
    hyst_mbps: float = 0.0
    min_dwell_sec: int = 0
    mode: str = "threshold"
    trend_deadband_mbps: float = 0.0
    level_bounds_mbps: tuple[float, ...] = (172.0, 305.0, 338.0)
    level_gnb2_pct: tuple[int, ...] = (0, 50, 70, 90)
    level_gnb1_pct: tuple[int, ...] = (30, 50, 70, 90)
    split_total_mbps: int = 1000
    decision_tick_sec: int = 0
    predict_period_sec: int = 0
    predict_lead_sec: int = 20
    predict_match_mbps: float = 30.0
    down_confirm_samples: int = 1


_DEFAULT = Gnb2DecisionConfig()
_MODES = ("threshold", "trend", "level")
_SPLIT_TOTAL_MAX_MBPS = 100_000

# 연동 중 NCOF 재기동 없이 임계를 바꿔 볼 수 있도록, 판정 틱마다 파일 수정 시각을 보고 바뀌었을 때만 다시 읽는다.
# (재기동은 복원 과도기에 통지가 유실되는 창을 만든다 — HANDOFF §8.1)
_cache: Gnb2DecisionConfig = _DEFAULT
_cache_key: tuple[str | None, float | None, tuple] | None = None


def _setting_file() -> str | None:
    """조회 우선순위: NCOF_SETTING_FILE 환경변수 > 코드 위치 기준 상위의 ncof_setting.conf."""
    return os.getenv("NCOF_SETTING_FILE") or _find_upwards("ncof_setting.conf")


_KEYS = (
    "GNB2_TH_MBPS",
    "GNB2_HYST_MBPS",
    "GNB2_MIN_DWELL_SEC",
    "GNB2_DECISION_MODE",
    "GNB2_TREND_DEADBAND_MBPS",
    "GNB2_LEVEL_BOUNDS_MBPS",
    "GNB2_LEVEL_GNB2_PCT",
    "GNB2_LEVEL_GNB1_PCT",
    "GNB2_SPLIT_TOTAL_MBPS",
    "GNB2_DECISION_TICK_SEC",
    "GNB2_PREDICT_PERIOD_SEC",
    "GNB2_PREDICT_LEAD_SEC",
    "GNB2_PREDICT_MATCH_MBPS",
    "GNB2_DOWN_CONFIRM_SAMPLES",
)


def _env_overrides() -> tuple:
    return tuple(os.getenv(k) for k in _KEYS)


def _parse(
    raw: dict[str, str | None], file_read: bool, previous: Gnb2DecisionConfig
) -> Gnb2DecisionConfig:
    """설정 파일이 있으면 **파일만** 본다(키가 없거나 비면 기본값). 파일이 없을 때만 OS 환경변수를 본다.
    잘못된 값이면 직전 설정을 유지한다.

    포트 설정(nrf._cfg)과 달리 파일이 우선이다 — run_http2.sh 가 이 파일을 `set -a` 로 통째로 export 하므로
    환경변수를 보면 기동 시점 값이 남아, 연동 중 키를 지우거나 고친 것이 반영되지 않는다.
    """

    def pick(key: str) -> str | None:
        value = raw.get(key) if file_read else os.getenv(key)
        return value.strip() if value and value.strip() else None

    def floats(key: str, default: tuple) -> tuple[float, ...]:
        text = pick(key)
        try:
            return tuple(float(v) for v in text.split(",")) if text else tuple(float(v) for v in default)
        except ValueError as e:
            raise ValueError(f"{key}={text!r}") from e

    try:
        th = float(pick("GNB2_TH_MBPS") or _DEFAULT.th_mbps)
        hyst = float(pick("GNB2_HYST_MBPS") or _DEFAULT.hyst_mbps)
        dwell_f = float(pick("GNB2_MIN_DWELL_SEC") or _DEFAULT.min_dwell_sec)
        band = float(pick("GNB2_TREND_DEADBAND_MBPS") or _DEFAULT.trend_deadband_mbps)
        if not all(math.isfinite(v) for v in (th, hyst, dwell_f, band)):
            raise ValueError("inf/nan")
        dwell = int(dwell_f)
    except (ValueError, OverflowError) as e:
        logger.warning(f"판정 설정 값이 숫자가 아님 — 직전 설정 유지: {e}")
        return previous
    mode = (pick("GNB2_DECISION_MODE") or _DEFAULT.mode).lower()
    if th <= 0 or hyst < 0 or hyst >= th or dwell < 0 or band < 0 or mode not in _MODES:
        logger.warning(
            f"판정 설정 범위 오류(TH>0, 0<=HYST<TH, DWELL>=0, DEADBAND>=0, MODE∈{_MODES}) — 직전 설정 유지: "
            f"TH={th} HYST={hyst} DWELL={dwell} MODE={mode} DEADBAND={band}"
        )
        return previous
    # level 키는 level 모드에서만 쓰인다 — 다른 모드에서 그 키가 잘못돼도 TH 변경·trend 롤백까지 막지 않는다
    try:
        bounds = floats("GNB2_LEVEL_BOUNDS_MBPS", _DEFAULT.level_bounds_mbps)
        pcts_f = floats("GNB2_LEVEL_GNB2_PCT", _DEFAULT.level_gnb2_pct)
        gnb1_f = floats("GNB2_LEVEL_GNB1_PCT", _DEFAULT.level_gnb1_pct)
        total_f = float(pick("GNB2_SPLIT_TOTAL_MBPS") or _DEFAULT.split_total_mbps)
        level_error = _level_error(bounds, pcts_f, total_f)
        # 키가 없는데 기본 gNB1 몫(4단계 · 총합 1000 기준)이 이 경계 개수나 총합과 안 맞으면
        # 설정 전체를 막지 않고 gNB1 쌍 분배만 끈다(gNB1 set 그대로) — 그 이유를 경고에 남긴다
        gnb1_off = None
        if pick("GNB2_LEVEL_GNB1_PCT") is None and not level_error:
            gnb1_off = _gnb1_level_error(bounds, gnb1_f, total_f)
            if gnb1_off:
                gnb1_f = ()
        level_error = level_error or _gnb1_level_error(bounds, gnb1_f, total_f)
    except ValueError as e:
        bounds, pcts_f, gnb1_f, total_f = (), (), (), 0.0
        gnb1_off = None
        level_error = f"숫자가 아님: {e}"
    if level_error:
        if mode == "level":
            logger.warning(
                f"판정 설정 단계 오류({level_error}) — 직전 설정 유지: "
                f"BOUNDS={bounds} PCT={pcts_f} GNB1_PCT={gnb1_f} TOTAL={total_f}"
            )
            return previous
        logger.warning(
            f"판정 설정 단계 오류({level_error}) — level 모드가 아니라 단계 값만 직전 값({_levels_text(previous)})을 둔다"
        )
        bounds, pcts_f, gnb1_f, total_f = (
            previous.level_bounds_mbps,
            previous.level_gnb2_pct,
            previous.level_gnb1_pct,
            float(previous.split_total_mbps),
        )
    pcts = tuple(int(p) for p in pcts_f)
    gnb1_pcts = tuple(int(p) for p in gnb1_f)
    tick, period, lead, match, confirm = _parse_timing(pick, previous)
    if mode == "level":
        # 두두원 UPF 는 3GPP 10%(DL_DISTRIBUTION_10) 를 atsss_support_10_pro 설정에 따라 0% 로 바꾼다.
        # 100% 는 그 쌍의 WLAN set 이 0 이 되어 하향이 전부 3GPP 다리로 간다.
        for name, values in (("gNB2", pcts), ("gNB1", gnb1_pcts)):
            risky = [p for p in values if p in (10, 100)]
            if risky:
                logger.warning(
                    f"판정 설정 단계 주의: {name} 몫 {risky}% — 10% 는 UPF 가 0% 로 볼 수 있고 100% 는 WLAN set 0"
                )
        if gnb1_off:
            default = "/".join(str(p) for p in _DEFAULT.level_gnb1_pct)
            logger.warning(
                f"판정 설정 단계 주의: GNB2_LEVEL_GNB1_PCT 가 없고 기본 gNB1 몫({default}%)을 이 설정에 쓸 수 없다"
                f"({gnb1_off}) — gNB1 쌍 분배를 끈다(gNB1 set 그대로)"
            )
    return Gnb2DecisionConfig(
        th_mbps=th,
        hyst_mbps=hyst,
        min_dwell_sec=dwell,
        mode=mode,
        trend_deadband_mbps=band,
        level_bounds_mbps=bounds,
        level_gnb2_pct=pcts,
        level_gnb1_pct=gnb1_pcts,
        split_total_mbps=int(total_f),
        decision_tick_sec=tick,
        predict_period_sec=period,
        predict_lead_sec=lead,
        predict_match_mbps=match,
        down_confirm_samples=confirm,
    )


def _parse_timing(pick, previous: Gnb2DecisionConfig) -> tuple[int, int, int, float, int]:
    """판정 틱 · 선제 판정 · 내림 확인 키. 잘못되면 이 다섯 값만 직전 값을 둔다(임계 · 단계 변경까지 막지 않는다)."""
    keep = (
        previous.decision_tick_sec,
        previous.predict_period_sec,
        previous.predict_lead_sec,
        previous.predict_match_mbps,
        previous.down_confirm_samples,
    )
    names = (
        "GNB2_DECISION_TICK_SEC",
        "GNB2_PREDICT_PERIOD_SEC",
        "GNB2_PREDICT_LEAD_SEC",
        "GNB2_PREDICT_MATCH_MBPS",
        "GNB2_DOWN_CONFIRM_SAMPLES",
    )
    defaults = (
        _DEFAULT.decision_tick_sec,
        _DEFAULT.predict_period_sec,
        _DEFAULT.predict_lead_sec,
        _DEFAULT.predict_match_mbps,
        _DEFAULT.down_confirm_samples,
    )
    texts = [pick(k) for k in names]
    try:
        tick, period, lead, match, confirm = (float(t) if t else float(d) for t, d in zip(texts, defaults))
        if not all(math.isfinite(v) for v in (tick, period, lead, match, confirm)):
            raise ValueError("inf/nan")
    except (ValueError, OverflowError) as e:
        logger.warning(f"판정 틱 · 선제 설정 값이 숫자가 아님 — 이 값들만 직전 설정 유지: {e}")
        return keep
    whole = all(v == int(v) for v in (tick, period, lead, confirm))
    if not whole or tick < 0 or period < 0 or lead < 1 or match <= 0 or not 1 <= confirm <= 10 or (period and period <= lead):
        logger.warning(
            "판정 틱 · 선제 설정 범위 오류(TICK·PERIOD 0 이상 정수, LEAD 1 이상 정수이고 PERIOD 가 있으면 그보다 작게, "
            "MATCH>0, DOWN_CONFIRM 1~10) — 이 값들만 직전 설정 유지: "
            + " ".join(f"{n.removeprefix('GNB2_')}={t}" for n, t in zip(names, texts) if t is not None)
        )
        return keep
    return int(tick), int(period), int(lead), match, int(confirm)


def _timing_text(cfg: Gnb2DecisionConfig) -> str:
    tick = f"{cfg.decision_tick_sec} s" if cfg.decision_tick_sec else "상향 repPeriod"
    if cfg.predict_period_sec:
        predict = (
            f"선제 주기 {cfg.predict_period_sec} s · 앞 {cfg.predict_lead_sec} s · 일치 {cfg.predict_match_mbps:g} Mbps"
        )
    else:
        predict = "선제 끔"
    return f"틱 {tick} · {predict} · 내림 확인 {cfg.down_confirm_samples}"


def _level_error(bounds: tuple[float, ...], pcts: tuple[float, ...], total: float) -> str | None:
    """level 단계 설정의 형식 오류를 설명하는 문자열, 없으면 None.

    두두원 UPF 는 gNB2 set 과 노트북2 WLAN set 의 mbr 비를 (int)(비율%) 로 버린 뒤 10% 단위로 올려 적용한다.
    그래서 gNB2 몫이 10 의 배수이고 split 이 정수 Mbps 여야 화면 값과 실제 적용 비율이 같다.
    """
    if not all(math.isfinite(v) for v in (*bounds, *pcts, total)):
        return "숫자가 아님(inf/nan)"
    if not bounds or any(b <= 0 for b in bounds):
        return "경계는 하나 이상, 모두 >0"
    if any(lo >= hi for lo, hi in zip(bounds, bounds[1:])):
        return "경계는 오름차순(같은 값 불가)"
    if len(pcts) != len(bounds) + 1:
        return "gNB2 몫 개수 = 경계 개수 + 1"
    if any(p != int(p) or int(p) % 10 or not 0 <= p <= 100 for p in pcts):
        return "gNB2 몫은 0~100 의 10 의 배수"
    if pcts[0] != 0 or any(p <= 0 for p in pcts[1:]):
        return "단계 0(DEEP_SLEEP)만 gNB2 몫 0"
    if any(lo > hi for lo, hi in zip(pcts, pcts[1:])):
        return "gNB2 몫은 비감소"
    if total <= 0 or total != int(total) or any(int(total) * int(p) % 100 for p in pcts):
        return "총합은 양의 정수이고 총합×몫/100 이 정수"
    if total > _SPLIT_TOTAL_MAX_MBPS:
        # 아주 큰 float 는 "1e+16 Mbps" 로 찍혀 14_e 모델 검증(^\d+(\.\d+)? …)에서 막힌다
        return f"총합은 {_SPLIT_TOTAL_MAX_MBPS} Mbps 이하"
    return None


def _gnb1_level_error(bounds: tuple[float, ...], pcts: tuple[float, ...], total: float) -> str | None:
    """gNB1 쌍 몫의 형식 오류 — gNB2 몫과 같은 격자 규칙이되 단계 0 이 0 일 필요는 없다(gNB1 은 잠들지 않는다).
    빈 값은 오류가 아니라 gNB1 쌍 분배 끔이다."""
    if not pcts:
        return None
    if not all(math.isfinite(v) for v in pcts):
        return "gNB1 몫이 숫자가 아님(inf/nan)"
    if len(pcts) != len(bounds) + 1:
        return "gNB1 몫 개수 = 경계 개수 + 1"
    if any(p != int(p) or int(p) % 10 or not 0 <= p <= 100 for p in pcts):
        return "gNB1 몫은 0~100 의 10 의 배수"
    if any(lo > hi for lo, hi in zip(pcts, pcts[1:])):
        return "gNB1 몫은 비감소"
    if any(int(total) * int(p) % 100 for p in pcts):
        return "총합×gNB1 몫/100 이 정수"
    return None


def _levels_text(cfg: Gnb2DecisionConfig) -> str:
    bounds = "/".join(f"{b:g}" for b in cfg.level_bounds_mbps)
    pcts = "/".join(str(p) for p in cfg.level_gnb2_pct)
    gnb1 = "/".join(str(p) for p in cfg.level_gnb1_pct) + "%" if cfg.level_gnb1_pct else "끔"
    return f"경계 {bounds} Mbps · gNB2 {pcts}% · gNB1 {gnb1} · 총 {cfg.split_total_mbps} Mbps"


def current_decision_config() -> Gnb2DecisionConfig:
    """현재 판정 설정을 반환한다. 설정 파일이나 관련 환경변수가 바뀌었을 때만 다시 읽는다."""
    global _cache, _cache_key
    path = _setting_file()
    try:
        mtime = os.path.getmtime(path) if path else None
    except OSError:
        mtime = None
    key = (path, mtime, _env_overrides())
    if key == _cache_key:
        return _cache

    try:
        file_read = bool(path) and mtime is not None
        raw = dict(dotenv_values(path)) if file_read else {}
        new = _parse(raw, file_read, _cache)
    except Exception as e:  # noqa: BLE001 — 인코딩(CP949 저장)·권한 오류 등. 판정 루프를 죽이면 안 된다
        logger.warning(f"판정 설정 파일을 읽지 못함 — 직전 설정 유지: {e} ({path})")
        _cache_key = key  # 같은 파일로 매 틱 같은 경고를 반복하지 않는다
        return _cache
    if _cache_key is not None and new != _cache:
        logger.warning(
            f"판정 설정 변경: TH {_cache.th_mbps} → {new.th_mbps} Mbps · "
            f"HYST {_cache.hyst_mbps} → {new.hyst_mbps} Mbps · "
            f"DWELL {_cache.min_dwell_sec} → {new.min_dwell_sec} s · "
            f"MODE {_cache.mode} → {new.mode} · "
            f"DEADBAND {_cache.trend_deadband_mbps} → {new.trend_deadband_mbps} Mbps · "
            f"LEVEL {_levels_text(_cache)} → {_levels_text(new)} · "
            f"{_timing_text(_cache)} → {_timing_text(new)} ({path})"
        )
    elif _cache_key is None:
        logger.info(
            f"판정 설정: TH {new.th_mbps} Mbps · HYST {new.hyst_mbps} Mbps · "
            f"DWELL {new.min_dwell_sec} s · MODE {new.mode} · "
            f"DEADBAND {new.trend_deadband_mbps} Mbps · LEVEL {_levels_text(new)} · {_timing_text(new)} ({path})"
        )
    _cache, _cache_key = new, key
    return new


_ON_VALUES = ("1", "true", "yes", "on")
_OFF_VALUES = ("0", "false", "no", "off")
_control_sequential_last: bool | None = None
_control_sequential_raw: str | None = None


def control_sequential() -> bool:
    """제어 순서 — 켜짐(기본)이면 gNB2 를 켤 때 15f ACTIVE → 200 → 14_e, 끌 때 14_e 0:100 → 200 → 15f DEEP_SLEEP 처럼
    앞 요청의 성공 응답을 받은 뒤 다음을 보낸다(10/26 두두원 회신). GNB2_CONTROL_SEQUENTIAL=0 이면 예전처럼 동시에 보낸다.

    재기동 없이 되돌릴 수 있도록 판정 설정과 같은 파일 · 같은 우선순위(파일이 있으면 파일만)로 보낼 때마다 읽는다.
    값이 비었거나 잘못되면 순차다.
    """
    global _control_sequential_last, _control_sequential_raw
    path = _setting_file()
    try:
        if path and os.path.exists(path):
            value = dict(dotenv_values(path)).get("GNB2_CONTROL_SEQUENTIAL")
        else:
            value = os.getenv("GNB2_CONTROL_SEQUENTIAL")
    except Exception as e:  # noqa: BLE001 — 제어 전송을 막으면 안 된다
        logger.warning(f"GNB2_CONTROL_SEQUENTIAL 를 읽지 못함 — 순차 전송: {e} ({path})")
        value = None
    text = (value or "").strip().lower()
    sequential = text not in _OFF_VALUES
    if text and text not in _ON_VALUES + _OFF_VALUES and text != _control_sequential_raw:
        logger.warning(f"GNB2_CONTROL_SEQUENTIAL 값 오류({value!r}, 1 또는 0) — 순차 전송")
    _control_sequential_raw = text
    if _control_sequential_last is not None and sequential != _control_sequential_last:
        logger.warning(
            f"제어 순서 설정 변경: {'순차' if _control_sequential_last else '동시'} → "
            f"{'순차' if sequential else '동시'} 전송 ({path})"
        )
    _control_sequential_last = sequential
    return sequential


def wlan_sub_rep_period() -> int | None:
    """WLAN_PERFORMANCE(12p_c) 하위 구독에 줄 repPeriod(초). 없거나 잘못되면 None(= 상향 repPeriod 를 따른다).

    두두원은 하위 repPeriod 를 송신 주기이자 12p_c 평균 창(udptp_traffic 최근 N초 AVG)으로 쓴다.
    판정 설정과 같은 파일·같은 우선순위(파일이 있으면 파일만)로 읽되, 하위 구독을 **만들 때만** 읽는다 —
    바꾸면 재구독(NCOF 재기동)해야 반영된다.
    """
    path = _setting_file()
    try:
        if path and os.path.exists(path):
            value = dict(dotenv_values(path)).get("WLAN_SUB_REP_PERIOD_SEC")
        else:
            value = os.getenv("WLAN_SUB_REP_PERIOD_SEC")
    except Exception as e:  # noqa: BLE001 — 구독 생성을 막으면 안 된다
        logger.warning(f"WLAN_SUB_REP_PERIOD_SEC 를 읽지 못함 — 상향 repPeriod 를 따른다: {e} ({path})")
        return None
    if value is None or not value.strip():
        return None
    try:
        period = int(value.strip())
    except ValueError:
        period = 0
    if period < 1:
        logger.warning(f"WLAN_SUB_REP_PERIOD_SEC 값 오류({value!r}, 1 이상 정수) — 상향 repPeriod 를 따른다")
        return None
    return period
