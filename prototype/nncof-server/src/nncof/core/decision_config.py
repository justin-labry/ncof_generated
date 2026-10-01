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
    """

    th_mbps: float = 500.0
    hyst_mbps: float = 0.0
    min_dwell_sec: int = 0


_DEFAULT = Gnb2DecisionConfig()

# 연동 중 NCOF 재기동 없이 임계를 바꿔 볼 수 있도록, 판정 틱마다 파일 수정 시각을 보고 바뀌었을 때만 다시 읽는다.
# (재기동은 복원 과도기에 통지가 유실되는 창을 만든다 — HANDOFF §8.1)
_cache: Gnb2DecisionConfig = _DEFAULT
_cache_key: tuple[str | None, float | None, tuple] | None = None


def _setting_file() -> str | None:
    """조회 우선순위: NCOF_SETTING_FILE 환경변수 > 코드 위치 기준 상위의 ncof_setting.conf."""
    return os.getenv("NCOF_SETTING_FILE") or _find_upwards("ncof_setting.conf")


def _env_overrides() -> tuple:
    return tuple(os.getenv(k) for k in ("GNB2_TH_MBPS", "GNB2_HYST_MBPS", "GNB2_MIN_DWELL_SEC"))


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

    try:
        th = float(pick("GNB2_TH_MBPS") or _DEFAULT.th_mbps)
        hyst = float(pick("GNB2_HYST_MBPS") or _DEFAULT.hyst_mbps)
        dwell_f = float(pick("GNB2_MIN_DWELL_SEC") or _DEFAULT.min_dwell_sec)
        if not (math.isfinite(th) and math.isfinite(hyst) and math.isfinite(dwell_f)):
            raise ValueError("inf/nan")
        dwell = int(dwell_f)
    except (ValueError, OverflowError) as e:
        logger.warning(f"판정 설정 값이 숫자가 아님 — 직전 설정 유지: {e}")
        return previous
    if th <= 0 or hyst < 0 or hyst >= th or dwell < 0:
        logger.warning(
            f"판정 설정 범위 오류(TH>0, 0<=HYST<TH, DWELL>=0) — 직전 설정 유지: "
            f"TH={th} HYST={hyst} DWELL={dwell}"
        )
        return previous
    return Gnb2DecisionConfig(th_mbps=th, hyst_mbps=hyst, min_dwell_sec=dwell)


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
            f"DWELL {_cache.min_dwell_sec} → {new.min_dwell_sec} s ({path})"
        )
    elif _cache_key is None:
        logger.info(
            f"판정 설정: TH {new.th_mbps} Mbps · HYST {new.hyst_mbps} Mbps · "
            f"DWELL {new.min_dwell_sec} s ({path})"
        )
    _cache, _cache_key = new, key
    return new
