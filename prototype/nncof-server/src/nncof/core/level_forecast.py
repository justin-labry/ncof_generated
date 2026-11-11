# level 모드 선제 판정 — 되풀이되는 bg 패턴을 한 주기 전 12p_c 로 내다본다

"""12p_c 이력으로 「앞으로 lead 초 안의 최대값」 을 예측한다.

12p_c 는 두두원이 udptp 수신량을 최근 W 초(WLAN 하위 repPeriod) 평균해 W 초마다 보내는 값이다. bg 가 같은 패턴을
주기 P 로 되풀이하면, 지금부터 lead 초 동안의 값은 한 주기 전 같은 구간의 12p_c 로 내다볼 수 있다.

- 시각 보정: W 초 이동평균은 실제 bg 보다 약 W/2 늦다 → 실제 시각 u 의 bg ≈ 이력의 (u - P + W/2) 값.
  샘플 사이는 직선 보간한다(계단의 이동평균은 길이 W 의 경사라 보간 오차가 경계 통과 시각으로 ±2초 안팎).
- 확인(게이트): 최근 한 주기(check 초) 샘플이 한 주기 전 같은 시각 값과 평균 오차 match_mbps 이하일 때만 예측을 쓴다 —
  패턴이 바뀌었거나 P 가 틀렸으면 예측을 끄고 지금 값으로만 판정한다(이유는 Forecast.reason). 중앙값이 아니라
  평균인 까닭: P 가 틀려도 평탄 구간은 맞아 보여서, 어긋남은 계단 근처에만 몰린다(380초 패턴을 340초로 보면 중앙값 20 · 평균 100 남짓).
  최근 6×W 초(약 1분)만 따로 봐서 평균 오차가 match_mbps 의 2배를 넘어도 끈다 — bg 송신기를 다시 띄워 위상이 바뀌면
  한 주기 평균은 천천히 커지지만 최근 창은 첫 어긋난 계단에서 바로 걸린다(틀린 선제가 한 계단 넘게 남지 않게).
- 이력은 메모리에만 있다 — NCOF 를 다시 띄우면 한 주기(+ check 초) 동안은 사후 판정만 한다.
"""

from __future__ import annotations

import bisect
import statistics
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Forecast:
    """peak_mbps = 앞으로 lead 초 안의 예측 최대값(None = 예측을 쓰지 않음). reason = 'ok' 또는 쓰지 않은 이유."""

    peak_mbps: float | None
    reason: str
    match_err_mbps: float | None = None


class PeriodicForecaster:
    """12p_c 샘플 이력 — (stream, timeStamp) 로 중복을 거르고 timeStamp 순으로 둔다. 여러 스트림(겹친 상향 쌍)이
    같은 udptp 표를 읽으므로 섞어 써도 된다(샘플이 촘촘해질 뿐)."""

    def __init__(self, retain_sec: float = 3600.0):
        self.retain_sec = retain_sec
        self._ts: list[float] = []
        self._val: list[float] = []
        self._seen: set[tuple[str, float]] = set()

    def __len__(self) -> int:
        return len(self._ts)

    def clear(self) -> None:
        self._ts.clear()
        self._val.clear()
        self._seen.clear()

    def seen(self, stream_id: str, ts: datetime) -> bool:
        return (stream_id, ts.timestamp()) in self._seen

    def add(self, stream_id: str, ts: datetime, mbps: float) -> bool:
        """새 샘플이면 넣고 True. 같은 (stream, timeStamp) 는 한 번만."""
        t = ts.timestamp()
        key = (stream_id, t)
        if key in self._seen:
            return False
        self._seen.add(key)
        i = bisect.bisect_right(self._ts, t)
        self._ts.insert(i, t)
        self._val.insert(i, float(mbps))
        cutoff = self._ts[-1] - self.retain_sec
        k = bisect.bisect_left(self._ts, cutoff)
        if k:
            del self._ts[:k]
            del self._val[:k]
            self._seen = {s for s in self._seen if s[1] >= cutoff}
        return True

    def recent(self, n: int, min_gap: float = 0.0) -> list[float]:
        """timeStamp 순 마지막 n 개 값(오래된 것 먼저). min_gap 초보다 가까운 샘플은 하나로 친다(가장 새것만) —
        12p_c 스트림이 둘 이상(PCF · RICF 쌍의 WLAN 하위 구독)이면 같은 10초 창을 두 번 받는데, 그것을 두 개로 세면
        내림 확인이 한 창으로 끝나 중간 단계를 거친다(11/04 16:14:02 실장비 — 두 구독을 0.3초 간격으로 만들어 위상이 같았다)."""
        out: list[float] = []
        last: float | None = None
        for t, v in zip(reversed(self._ts), reversed(self._val)):
            if len(out) >= n:
                break
            if last is None or last - t >= min_gap:
                out.append(v)
                last = t
        return out[::-1]

    def value_at(self, t: float, max_gap: float) -> float | None:
        """epoch 초 t 의 직선 보간 값. 이력 밖이거나 양옆 샘플 간격이 max_gap 초를 넘으면 None."""
        ts = self._ts
        if not ts or t < ts[0] or t > ts[-1]:
            return None
        i = bisect.bisect_left(ts, t)
        if ts[i] == t:
            return self._val[i]
        lo, hi = i - 1, i
        gap = ts[hi] - ts[lo]
        if gap > max_gap:
            return None
        return self._val[lo] + (t - ts[lo]) / gap * (self._val[hi] - self._val[lo])

    def forecast(
        self,
        now: datetime,
        period_sec: float,
        lead_sec: float,
        window_sec: float,
        match_mbps: float,
        check_sec: float | None = None,
    ) -> Forecast:
        """now 부터 lead 초 동안의 예측 최대값. 쓸 수 없으면 peak_mbps=None 과 이유."""
        if period_sec <= 0 or lead_sec <= 0:
            return Forecast(None, "선제 끔")
        n = now.timestamp()
        max_gap = 2.5 * window_sec
        check_sec = check_sec or period_sec

        # 1) 게이트 — 최근 한 주기가 그 앞 주기와 같은 패턴인가
        k = bisect.bisect_left(self._ts, n - check_sec)
        errs = [
            abs(v - ref)
            for t, v in zip(self._ts[k:], self._val[k:])
            if (ref := self.value_at(t - period_sec, max_gap)) is not None
        ]
        need = max(3, int(check_sec / window_sec) // 2)
        if len(errs) < need:
            return Forecast(None, f"이력 부족(한 주기 전과 비교한 샘플 {len(errs)}/{need})")
        err = statistics.fmean(errs)
        if err > match_mbps:
            return Forecast(None, f"패턴 불일치(한 주기 전 대비 평균 오차 {err:.0f} > {match_mbps:g} Mbps)", err)
        k = bisect.bisect_left(self._ts, n - 6 * window_sec)
        recent = [
            abs(v - ref)
            for t, v in zip(self._ts[k:], self._val[k:])
            if (ref := self.value_at(t - period_sec, max_gap)) is not None
        ]
        if len(recent) >= 3 and (r := statistics.fmean(recent)) > 2 * match_mbps:
            return Forecast(None, f"최근 어긋남(최근 {6 * window_sec:g}초 평균 오차 {r:.0f} > {2 * match_mbps:g} Mbps)", err)

        # 2) 예측 — 실제 [now, now+lead] ≈ 이력 [now-P+W/2, now-P+W/2+lead]
        a = n - period_sec + window_sec / 2
        b = a + lead_sec
        ends = (self.value_at(a, max_gap), self.value_at(b, max_gap))
        if ends[0] is None or ends[1] is None:
            return Forecast(None, "한 주기 전 이력이 비어 있음", err)
        i, j = bisect.bisect_right(self._ts, a), bisect.bisect_left(self._ts, b)
        points = [a, *self._ts[i:j], b]
        if any(y - x > max_gap for x, y in zip(points, points[1:])):
            return Forecast(None, "한 주기 전 이력이 끊겨 있음", err)
        return Forecast(max(ends[0], ends[1], *self._val[i:j]), "ok", err)
