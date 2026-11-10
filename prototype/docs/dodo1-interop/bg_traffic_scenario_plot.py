"""시연 시나리오(2026-11-04 칠판) — 백그라운드 트래픽 패턴 그래프.

사용: uv run --no-project --with matplotlib python bg_traffic_scenario_plot.py [출력.png]
구간 값을 바꾸려면 SEGMENTS 만 고친다(1주기 = 구간 길이 합, 그대로 반복).
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

# (Mbps, 초, NCOF 판정, 3GPP:WiFi)
SEGMENTS = [
    (70, 120, "DeepSleep", "0:10"),
    (200, 40, "Active", "3:7"),
    (300, 40, "Active", "5:5"),
    (400, 40, "Active", "10:0"),
    (530, 60, "Active", "10:0"),
    (300, 40, "Active", "5:5"),
]
# NCOF 판정 단계 (하한, 상한, 이름) — 칠판 표
LEVELS = [
    (0, 150, "L1  DeepSleep · 0:10"),
    (150, 250, "L2  Active · 3:7"),
    (250, 350, "L3  Active · 5:5"),
    (350, 450, "L4  Active · 10:0"),
    (450, 600, "L5  Active · 10:0  (~1500)"),
]
CYCLES = 2
Y_MAX = 600

SURFACE = "#fcfcfb"
TEXT_1 = "#0b0b0b"
TEXT_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#d9d8d3"
BAND = "#f1f0ec"
SERIES = "#2a78d6"


def pick_font() -> None:
    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("NanumGothic", "NanumBarunGothic", "Noto Sans CJK KR", "Baekmuk Gulim"):
        if cand in names:
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams["axes.unicode_minus"] = False


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "bg_traffic_scenario.png"
    pick_font()
    period = sum(d for _, d, _, _ in SEGMENTS)
    x_end = period * CYCLES

    # 계단 좌표
    xs, ys, bounds = [], [], []
    t = 0
    for _ in range(CYCLES):
        for rate, dur, _, _ in SEGMENTS:
            xs.append(t)
            ys.append(rate)
            bounds.append(t)
            t += dur
    bounds.append(t)
    tail = period * 0.08  # 다음 주기 첫 구간을 조금 보여 준다
    xs += [t, t + tail]
    ys += [SEGMENTS[0][0], SEGMENTS[0][0]]
    x_lim = t + tail

    fig, ax = plt.subplots(figsize=(14, 6.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # 판정 단계 띠 + 경계선 + 오른쪽 이름
    for i, (lo, hi, name) in enumerate(LEVELS):
        if i % 2 == 0:
            ax.axhspan(lo, hi, color=BAND, zorder=0, lw=0)
        if lo > 0:
            ax.axhline(lo, color=GRID, lw=0.9, ls=(0, (4, 3)), zorder=1)
        ax.text(x_lim + period * 0.03, (lo + hi) / 2, name, va="center", ha="left",
                fontsize=10.5, color=TEXT_2, clip_on=False)
    ax.text(x_lim + period * 0.03, Y_MAX + 14, "NCOF 판정 단계 · 3GPP:WiFi", va="bottom",
            ha="left", fontsize=10, color=MUTED, clip_on=False)

    # 주기 경계
    for c in range(1, CYCLES):
        ax.axvline(period * c, color=MUTED, lw=1.0, zorder=2)
        ax.text(period * c + 4, Y_MAX - 12, f"{period}초마다 같은 패턴 반복 →", va="top",
                ha="left", fontsize=10, color=TEXT_2)

    # 트래픽 계단
    ax.step(xs, ys, where="post", color=SERIES, lw=2.4, zorder=3, solid_joinstyle="round")

    # 첫 주기 구간 이름(선택적 직접 라벨)
    t = 0
    for rate, dur, state, ratio in SEGMENTS:
        mid = t + dur / 2
        wide = dur >= 100  # 좁은 40·60초 구간은 숫자만(단계 이름은 오른쪽 띠)
        ax.text(mid, rate + 12, f"{rate} Mbps" if wide else f"{rate}", ha="center",
                va="bottom", fontsize=11, color=TEXT_1, fontweight="bold", zorder=4)
        sub = f"{dur}초\n{state} {ratio}" if wide else f"{dur}초\n{ratio}"
        ax.text(mid, rate - 12, sub, ha="center", va="top",
                fontsize=9.5, color=TEXT_2, linespacing=1.3, zorder=4)
        t += dur

    ax.set_xlim(0, x_lim)
    ax.set_ylim(0, Y_MAX)
    ax.set_xticks(bounds)
    ax.set_xticklabels([str(b) for b in bounds], fontsize=9, color=TEXT_2)
    ax.set_yticks(range(0, Y_MAX + 1, 100))
    ax.tick_params(axis="y", labelsize=9.5, colors=TEXT_2)
    ax.tick_params(axis="both", length=0, pad=6)
    ax.set_xlabel("시간 (초)", fontsize=11, color=TEXT_2, labelpad=8)
    ax.set_ylabel("백그라운드 트래픽 (Mbps)", fontsize=11, color=TEXT_2, labelpad=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)

    fig.text(0.06, 0.955, f"백그라운드 트래픽 패턴 — 1주기 {period}초, 계속 반복",
             fontsize=15, color=TEXT_1, fontweight="bold", ha="left")
    steps = " → ".join(f"{r}({d}초)" for r, d, _, _ in SEGMENTS)
    fig.text(0.06, 0.915, f"{steps} → 처음으로 (Mbps)   ·   점선 = NCOF 판정 경계 150 / 250 / 350 / 450 Mbps",
             fontsize=10, color=TEXT_2, ha="left")

    fig.subplots_adjust(left=0.06, right=0.80, top=0.86, bottom=0.10)
    fig.savefig(out, facecolor=SURFACE)
    print(out, period, "s/cycle")


if __name__ == "__main__":
    main()
