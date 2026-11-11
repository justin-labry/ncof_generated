"""level 모드 선제 판정 오프라인 재연 — bg 계단 시나리오를 12p_c 로 바꿔 NCOF 판정 시각을 잰다.

모형(실장비에 맞춤):
- bg: SEGMENTS 를 주기적으로 되풀이(초 단위). 12p_c = 최근 W 초 평균, W 초마다(위상은 무작위), ±noise 배수 잡음.
- 12p_c 는 timeStamp 뒤 0.5 ~ 2.5 초에 NCOF 에 닿는다(10/29 · 11/04 측정 범위).
- NCOF 판정 틱 TICK 초(위상 무작위). 틱마다 data_analyzer 와 같은 순서: 이력에 새 샘플 → 최신 샘플로
  PeriodicForecaster.forecast → Gnb2RuleEngine.update_state(recent_mbps, forecast_mbps).

사용(prototype/nncof-server 에서):
  PYTHONPATH=src ../.venv/bin/python -I ../docs/dodo1-interop/tools/level_predict_sim.py [--runs 300] [--png out.png]
"""

from __future__ import annotations

import argparse
import dataclasses
import random
import statistics
import sys
from datetime import datetime, timedelta, timezone

from nncof.core.decision_config import Gnb2DecisionConfig
from nncof.core.gnb2_rule_engine import Gnb2RuleEngine
from nncof.core.level_forecast import PeriodicForecaster

# (Mbps, 초) — 2026-11-04 칠판 시나리오
SEGMENTS = [(70, 120), (200, 40), (300, 40), (400, 40), (530, 60), (300, 40)]
CONFIG = Gnb2DecisionConfig(
    mode="level",
    level_bounds_mbps=(150.0, 250.0, 350.0, 450.0),
    level_gnb2_pct=(0, 30, 50, 100, 100),
    level_gnb1_pct=(50, 50, 50, 50, 50),
    decision_tick_sec=2,
    predict_period_sec=340,
    predict_lead_sec=18,
    predict_match_mbps=30.0,
    down_confirm_samples=2,
)
W = 10  # 12p_c 평균 창 = WLAN 하위 repPeriod
BASE = datetime(2026, 11, 4, 6, 0, tzinfo=timezone.utc)


def bg_at(t: float, period: float) -> float:
    u = t % period
    for rate, dur in SEGMENTS:
        if u < dur:
            return rate
        u -= dur
    return SEGMENTS[0][0]


def run(seed: int, cycles: int, period_true: float, noise: float, cfg: Gnb2DecisionConfig = CONFIG):
    rng = random.Random(seed)
    sample_phase = rng.uniform(0, W)
    tick_phase = rng.uniform(0, cfg.decision_tick_sec)
    horizon = period_true * cycles
    # 12p_c 샘플 (timeStamp, 값, 도착)
    samples = []
    ts = sample_phase + W
    while ts < horizon:
        avg = statistics.fmean(bg_at(ts - W + k + 0.5, period_true) for k in range(W))
        samples.append((ts, avg * (1 + rng.uniform(-noise, noise)), ts + rng.uniform(0.5, 2.5)))
        ts += W
    engine = Gnb2RuleEngine()
    engine.apply_config(cfg)
    fc = PeriodicForecaster()
    k = 0
    newest = None
    timeline = []  # (t, level, note)
    t = tick_phase
    while t < horizon:
        while k < len(samples) and samples[k][2] <= t:
            s_ts, s_val, _ = samples[k]
            fc.add("wlan", BASE + timedelta(seconds=s_ts), s_val)
            newest = (s_ts, s_val)
            k += 1
        if newest is not None:
            now = BASE + timedelta(seconds=t)
            f = fc.forecast(now, cfg.predict_period_sec, cfg.predict_lead_sec, W, cfg.predict_match_mbps)
            before = engine.last_emitted_level
            engine.update_state(
                newest[1],
                now.isoformat(),
                recent_mbps=fc.recent(cfg.down_confirm_samples),
                forecast_mbps=f.peak_mbps if cfg.predict_period_sec else None,
            )
            if engine.last_emitted_level != before:
                timeline.append((t, engine.last_emitted_level, engine.last_level_note or ""))
        t += cfg.decision_tick_sec
    return timeline


def level_of(rate: float) -> int:
    return sum(rate >= b for b in CONFIG.level_bounds_mbps)


def step_times(period: float, cycles: int):
    """(시각, 이전 단계, 다음 단계) — bg 단계가 바뀌는 순간(1초 해상도로 bg 를 훑는다)."""
    out = []
    prev = level_of(bg_at(-0.5, period))
    for k in range(int(period * cycles)):
        lv = level_of(bg_at(k + 0.5, period))
        if lv != prev:
            out.append((float(k), prev, lv))
        prev = lv
    return out


def measure(timeline, steps, skip_until: float):
    """bg 계단마다 NCOF 가 그 단계에 처음 닿은 시각 - 계단 시각(음수 = 앞섬)과, 내릴 때 거친 중간 단계."""
    rows = []
    for T, lo, hi in steps:
        if T < skip_until:
            continue
        window = [(t, lv, note) for t, lv, note in timeline if T - 60 <= t <= T + 60]
        hit = next(((t, note) for t, lv, note in window if lv == hi), None)
        if hit is None:
            # 이미 그 단계였을 수 있다(선제 유지) — 직전 기록으로 판단
            before = [lv for t, lv, _ in timeline if t <= T]
            rows.append((T, lo, hi, None if not before or before[-1] != hi else float("-inf"), "", []))
            continue
        mids = [lv for t, lv, _ in window if T - 60 <= t < hit[0] and min(lo, hi) < lv < max(lo, hi)]
        rows.append((T, lo, hi, hit[0] - T, hit[1], mids))
    return rows


def main() -> None:
    global CONFIG
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--cycles", type=int, default=5)
    ap.add_argument("--noise", type=float, default=0.03)
    ap.add_argument("--period-true", type=float, default=340.0, help="실제 bg 주기(설정 340 과 다르게 줘 볼 것)")
    ap.add_argument("--tick", type=int, default=CONFIG.decision_tick_sec)
    ap.add_argument("--lead", type=int, default=CONFIG.predict_lead_sec)
    ap.add_argument("--confirm", type=int, default=CONFIG.down_confirm_samples)
    ap.add_argument("--png")
    a = ap.parse_args()
    CONFIG = dataclasses.replace(
        CONFIG, decision_tick_sec=a.tick, predict_lead_sec=a.lead, down_confirm_samples=a.confirm
    )
    period = a.period_true
    steps = step_times(period, a.cycles)
    by_kind: dict[tuple[int, int], list[float]] = {}
    mids_total = 0
    missing = 0
    for seed in range(a.runs):
        tl = run(seed, a.cycles, period, a.noise, CONFIG)
        for T, lo, hi, dt, note, mids in measure(tl, steps, skip_until=2 * period):
            if dt is None:
                missing += 1
                continue
            by_kind.setdefault((lo, hi), []).append(dt)
            mids_total += bool(mids)
    print(f"bg 주기 {period:g}초 · 설정 {CONFIG.predict_period_sec}초 · 틱 {CONFIG.decision_tick_sec}초 · 앞 {CONFIG.predict_lead_sec}초"
          f" · 내림 확인 {CONFIG.down_confirm_samples} · 잡음 ±{a.noise:.0%} · {a.runs}회 × 3주기째부터")
    print(f"{'계단(단계)':<12}{'n':>5}{'최소':>8}{'중앙':>8}{'최대':>8}   (초, 음수 = bg 보다 먼저)")
    for (lo, hi), v in sorted(by_kind.items(), key=lambda kv: (kv[0][0] < kv[0][1], kv[0])):
        print(f"L{lo + 1}→L{hi + 1:<8}{len(v):>5}{min(v):>8.1f}{statistics.median(v):>8.1f}{max(v):>8.1f}")
    print(f"내릴 때 중간 단계를 거친 경우 {mids_total} · 측정 못 함 {missing}")
    if a.png:
        plot(a.png, run(7, 4, period, a.noise, CONFIG), period)


def plot(path: str, timeline, period: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("NanumGothic", "NanumBarunGothic", "Noto Sans CJK KR"):
        if cand in names:
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams["axes.unicode_minus"] = False
    surface, text1, text2, grid, band = "#fcfcfb", "#0b0b0b", "#52514e", "#d9d8d3", "#f1f0ec"
    bg_c, ncof_c = "#2a78d6", "#d95f02"
    bounds = CONFIG.level_bounds_mbps
    edges = [0.0, *bounds, 600.0]
    names_lv = ["L1 DeepSleep 0:10", "L2 Active 3:7", "L3 Active 5:5", "L4 Active 10:0", "L5 Active 10:0"]
    c0 = 2 * period  # 세 번째 주기(예측이 켜진 뒤)
    t_lo, t_hi = c0 - 20, c0 + period + 45

    fig, ax = plt.subplots(figsize=(14, 6.6), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    for i in range(5):
        if i % 2 == 0:
            ax.axhspan(edges[i], edges[i + 1], color=band, lw=0, zorder=0)
        if i:
            ax.axhline(edges[i], color=grid, lw=0.9, ls=(0, (4, 3)), zorder=1)
        ax.text(t_hi - c0 + 6, (edges[i] + edges[i + 1]) / 2, names_lv[i], va="center", ha="left", fontsize=10.5,
                color=text2, clip_on=False)

    xs = [t / 1 for t in range(int(t_lo), int(t_hi) + 1)]
    ax.step([x - c0 for x in xs], [bg_at(x, period) for x in xs], where="post", color=bg_c, lw=2.4, zorder=3,
            label="백그라운드 트래픽 (Mbps)")
    # NCOF 단계 → 띠 가운데 높이로
    mid = [(edges[i] + edges[i + 1]) / 2 for i in range(5)]
    lv_t = [(t, lv, note) for t, lv, note in timeline]
    cur = max((lv for t, lv, _ in lv_t if t <= t_lo), default=0)
    seq_x, seq_y = [t_lo - c0], [mid[cur]]
    for t, lv, note in lv_t:
        if t_lo < t < t_hi:
            seq_x.append(t - c0)
            seq_y.append(mid[lv])
    seq_x.append(t_hi - c0)
    seq_y.append(seq_y[-1])
    ax.step(seq_x, seq_y, where="post", color=ncof_c, lw=2.0, zorder=4, label="NCOF 판정 단계 (띠 가운데)")
    # 계단마다 몇 초 앞섰나/늦었나
    for T, lo, hi in step_times(period, 4):
        if not (c0 <= T <= c0 + period):
            continue
        hit = next((t for t, lv, _ in lv_t if lv == hi and T - 60 <= t <= T + 60), None)
        if hit is None:
            continue
        dt = hit - T
        up = hi > lo
        y = mid[hi] + (14 if up else -14)
        same = CONFIG.level_gnb2_pct[lo] == CONFIG.level_gnb2_pct[hi] and lo > 0
        ax.annotate(f"{dt:+.0f}초" + (" (명령 같음)" if same else ""), (hit - c0, mid[hi]), xytext=(hit - c0 - (4 if up else -4), y),
                    ha="right" if up else "left", va="bottom" if up else "top", fontsize=10, color=text1,
                    fontweight="bold")
    ax.set_xlim(t_lo - c0, t_hi - c0)
    ax.set_ylim(0, 600)
    ticks = [0, 120, 160, 200, 240, 300, 340]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(v) for v in ticks], fontsize=9, color=text2)
    ax.tick_params(axis="y", labelsize=9.5, colors=text2)
    ax.tick_params(axis="both", length=0, pad=6)
    ax.set_xlabel("주기 안 시간 (초)", fontsize=11, color=text2, labelpad=8)
    ax.set_ylabel("Mbps", fontsize=11, color=text2, labelpad=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(grid)
    leg = ax.legend(loc="upper left", frameon=False, fontsize=10)
    for t in leg.get_texts():
        t.set_color(text2)
    fig.text(0.06, 0.955, "NCOF 판정 재연 — 오를 때 선제 · 내릴 때 사후 (세 번째 주기)", fontsize=15, color=text1,
             fontweight="bold", ha="left")
    fig.text(0.06, 0.915,
             f"판정 틱 {CONFIG.decision_tick_sec}초 · 한 주기({CONFIG.predict_period_sec}초) 전 12p_c 로 앞 {CONFIG.predict_lead_sec}초 예측"
             f" · 내릴 때 12p_c {CONFIG.down_confirm_samples}개 확인 · 숫자 = bg 계단 대비 NCOF 단계 변경 시각",
             fontsize=10, color=text2, ha="left")
    fig.subplots_adjust(left=0.06, right=0.82, top=0.86, bottom=0.10)
    fig.savefig(path, facecolor=surface)
    print(path)


if __name__ == "__main__":
    sys.exit(main())
