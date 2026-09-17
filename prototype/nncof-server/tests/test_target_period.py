# targetPeriod 생성 규칙 검증 — 두두원 우회 패치 A 의 분리를 고정한다.
#
# 배경: 2026-09-17 이전에는 `_DODO1_NO_FRACTIONAL_SECONDS` 하나가
#   (a) 마이크로초 제거 (두두원 ISO8601 파서 우회) 와
#   (b) startTime 60초 백데이트 (양측 시계 오차 마진)
# 를 **함께** 게이트했다. 두두원 파서가 고쳐져 (a) 를 회수할 때 (b) 까지 같이
# 사라지면, 회수 후 실패했을 때 원인이 소수 초인지 시계 오차인지 구분할 수 없다.
# 그래서 둘을 분리했고, 이 테스트가 그 분리를 고정한다.

from datetime import datetime, timedelta, timezone

import pytest

from nncof.core import subscription_request_builder as builder

_KST = timezone(timedelta(hours=9))


def _window():
    tw = builder._build_target_period(None)
    start = getattr(tw, "start_time", None) or tw.startTime
    stop = getattr(tw, "stop_time", None) or tw.stopTime
    return start, stop


@pytest.fixture
def restore_flag():
    original = builder._DODO1_NO_FRACTIONAL_SECONDS
    yield
    builder._DODO1_NO_FRACTIONAL_SECONDS = original


def test_backdate_applies_when_fractional_seconds_are_kept(restore_flag):
    """플래그 해제(현행) — 소수 초는 실리고 백데이트는 적용된다."""
    builder._DODO1_NO_FRACTIONAL_SECONDS = False
    before = datetime.now(_KST)
    start, _ = _window()

    assert start <= before - builder._DODO1_START_BACKDATE + timedelta(seconds=1)
    assert start >= before - builder._DODO1_START_BACKDATE - timedelta(seconds=5)


def test_backdate_survives_when_fractional_seconds_are_stripped(restore_flag):
    """플래그 복원 — 마이크로초는 제거되지만 백데이트는 **그대로 유지**된다.

    이것이 분리의 핵심이다. 회귀하면 두 완화가 다시 한 덩어리가 된다.
    """
    builder._DODO1_NO_FRACTIONAL_SECONDS = True
    before = datetime.now(_KST)
    start, stop = _window()

    assert start.microsecond == 0
    assert stop.microsecond == 0
    assert start <= before - builder._DODO1_START_BACKDATE + timedelta(seconds=1)


def test_fractional_seconds_present_while_patch_withdrawn(restore_flag):
    """회수 상태에서는 마이크로초가 살아 있어야 두두원 파서를 실증할 수 있다.

    startTime 은 백데이트로 정수 초가 될 확률이 있으므로 stopTime 으로 판정한다
    (stopTime = now + DEFAULT_MON_DURATION 이라 now 의 마이크로초를 그대로 물려받는다).
    """
    builder._DODO1_NO_FRACTIONAL_SECONDS = False
    _, stop = _window()
    assert stop.microsecond != 0, "회수 상태인데 마이크로초가 제거됐다"


def test_start_precedes_stop_in_both_modes(restore_flag):
    for flag in (True, False):
        builder._DODO1_NO_FRACTIONAL_SECONDS = flag
        start, stop = _window()
        assert start < stop, f"flag={flag} 에서 start >= stop"
