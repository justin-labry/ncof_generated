# ETRI 두두원 — Lyapunov(DPP) 결정엔진 적용계획 (v2)

> 출처: `ETRI_두두원_수식화_간결버전.md` (정정된 구현 스펙, 박세형/ETRI · 자매 정식화: 이루온–고려대 곽정호팀)
> 대상 코드베이스: `ncof_generated/prototype` (main @ `6c64fc6`) · 자매 룰: `ncof_yaml-main/tools/`
> 작성: Claude Code (Opus 4.8 종합 + Fable 5 설계 + 코드베이스 실측 검증) · 2026-07-18 갱신(v2)
> **전제(중요)**: 현재 개발 중이며, **개발 완료 후** Lyapunov를 적용하는 계획이다. RAN/core가 지금은 WLAN(12p_c)만 올려보내지만, **목표 상태에서 8p·13p_d·9p 등 실측 텔레메트리가 모두 정상 수신된다고 가정**한다. 따라서 큐·레이트·지연·전력을 "프록시/시뮬전용"이 아니라 **목표시점 가용값**으로 다루되, 그 값을 채우고 읽는 데 필요한 개발 항목은 분리해 명시한다.
> **v1 대비 정정**: §1(토폴로지 2-UE로 교정)·§0.1(변경점 요약) 참조. v1(집계 단일사용자 모델)은 **토폴로지 오류**가 있었다.

---

## 0. 한 줄 결론

> **목표 텔레메트리 하에서 충실한 구현이 가능하다.** `Gnb2LyapunovEngine`은 `Gnb2RuleEngine`을 상속한 **순수 파이썬 ~180–200줄**(numpy 불요)로 구현된다. 결정 코어(**s 열거 + 정확한 2-UE water-filling**)는 커플링 제약이 WLAN 용량 하나뿐이고 UE가 2명·경로가 각 2개라 **닫힌형 그리디가 LP의 정확해**(휴리스틱 아님) — 데크의 "수십 줄" 주장이 정직하게 성립한다. 필요한 모든 입력에 실제 반송자가 있다: `W`←12p_c(오늘 배선됨), per-UE `λ_u/D̂_u`←8p QOS_MONITORING, `R_g2/powerState`←13p_d, `D^max_u`←9p PERF_DATA — **네 이벤트군 모두 이미 구독됨**(`subscription_request_builder.py:177-178,:298,:421`), 공유 `notif_data_store`에 `notif_id`로 적재. 큐 `Q_u^j`·가상큐 `Z_u`는 텔레메트리 공백이 아니라 **표준 Lyapunov 합성 상태**다.

**개발이 먼저 착지해야 하는 것**(모두 additive, 아키텍처 변경 아님):
1. mock/실 NF가 매 주기 8p/13p_d/9p를 **실제로 push** (구독은 있으나 런타임 수신 미검증).
2. **per-SUPI 추출기** 신설(`extract_wlan_dl_mbps`는 SUPI를 합산해 스칼라로 뭉갬).
3. `DataAnalyzer`가 store에서 3개 kwarg를 조립해 `generate_notification` 호출부(`data_analyzer.py:207`)에 전달.
4. RSRP/SINR→rate 표 + 측정된 `ΔP_g2`(13p_d 회귀)로 config 상수 대체.
5. 엔진 상태 영속(`DataAnalyzer.stop()`이 엔진 재생성·`data_analyzer.py:95` → Q/Z 소거 방지).

엔진은 이벤트군이 없으면 **config 상수로 graceful degrade** — 그게 바로 Phase 1이다.

---

## 0.1 v1 → v2 변경점 (무엇이·왜 달라졌나)

이전 계획(v1, pptx 기반)의 핵심 오류는 **토폴로지 오독**이었다. 정정 스펙(`.md`)이 이를 바로잡았다.

| # | v1 (오류) | v2 (정정) | 영향 |
|---|---|---|---|
| 1 | **집계 단일사용자**가 `{g1,g2,w}` 3경로 심플렉스 | **2-UE·각 2경로**: `J₁={g1,w}`, `J₂={g2,w}` | v1은 UE1→gNB2 같은 **토폴로지가 금지한 라우팅**을 허용. gNB1→UE1 전용, gNB2→UE2 전용, WLAN 공유 |
| 2 | `s`가 집계 트래픽을 게이팅 | **gNB2는 UE2 전용** → `s`는 UE2의 3GPP 옵션만 게이팅. wake-up 합은 `g2∈J_u`인 u(=UE2)만 | v1은 UE1 백로그를 gNB2 이득에 잘못 가산해 **wake 이득 과대평가** |
| 3 | `s=0` 커플링 없음 | `s=0` ⇒ `feas(UE2)={w}`, `θ_w_2=1` **하드 게이팅**(soft penalty 아님) | v1은 gNB2 sleep 손실을 gNB1으로 흡수시켜 **WLAN 압력 과소평가 → 너무 쉽게 sleep** |
| 4 | σ·water-fill "축퇴/공허" | **진짜 2-UE LP**: 압력차 `Δ_u` 내림차순 greedy, 용량 소진점 1 UE만 분수 | v1은 정렬할 per-UE 구조 자체가 없었음 |
| 5 | 텔레메트리 대부분 **프록시/시뮬전용** | **목표시점 full-telemetry 가정** + "populate/read 개발필요"로 정직 분리 | 사용자 지시 반영. per-SUPI `λ_u/D̂_u`가 **load-bearing** |
| 6 | 직접 wake-up test(`δ_θ` 별도추정) | **s 열거**(동치·더 견고): 각 s의 water-fill 비용 argmin | `δ_θ`를 별도 추정할 필요 없음 |
| 7 | (mock 단일전력 기준) V* 도출 | **V0 warm-start 비순환화 수정** + **Z 가상큐 실사용화**(inverse-rate 가중) + **s-enum≡wake test 증명** | 스펙의 순환식·Z 미사용 결함을 설계에서 교정(§3) |
| 8 | `_decide(metric)`만 오버라이드 | `generate_notification` 오버라이드 + **3 additive kwarg**(8p/13p_d/9p) + DataAnalyzer store-scan | v1은 단일 스칼라만 받는 계약을 못 벗어남 |
| 9 | "R1–R5 존재 안 함, 과대주장 경고" | **R1–R5는 자매 repo `ncof_yaml`에 존재** → DPP 안전면으로 매핑(R1=구조, R3=V·ΔP, R4=용량, R5=Z) | v1 검증이 `ncof_generated`만 봐서 생긴 오판 |
| 10 | (에너지) 단일 상대전력 | gNB1 상시(`P_cst` **결정무관·소거**), per-bit `e_u^j`는 자기 gNB만, WLAN tx=0·CN `κ_w` | R1(primary always-on) 반영 |

---

## 1. 토폴로지 & 표기 (정정된 실제 PoC)

```
UE1 ──▶ 3GPP gNB1 (상시 ON) ─┐
   └──▶ Non-3GPP WLAN ───────┼──▶ UPF/Anchor ──▶ DN/App
UE2 ──▶ 3GPP gNB2 (가변 s) ──┤
   └──▶ Non-3GPP WLAN ───────┘   (WLAN은 UE1·UE2 공유, UPF로 종단)
```

- **접속집합** `J_u`: `J₁={g1,w}`, `J₂={g2,w}`. gNB1→UE1 전용, gNB2→UE2 전용, WLAN 공유.
- **핵심**: gNB2가 UE2 전용이라 `s=0`이면 UE2는 3GPP 경로 상실 → **UE2 트래픽 전부 WLAN**(`θ_w_2=1`).
- **결정변수**: `s∈{0,1}`(gNB2 ACTIVE/DEEP_SLEEP) · `σ_u∈{0,1}, σ_u≤s`(PoC는 UE2만) · `θ_u∈Δ^{J_u}`(접속별 분할비).

---

## 2. 수식 → 코드 매핑 (목표 텔레메트리 기준)

상태: **가용**(오늘 배선) / **도출**(엔진 내부) / **개발필요**(구독은 됨, populate/read 필요) / **설정**(config).

| 기호 | 의미 | 코드 반송자 / 도출 | 상태 |
|---|---|---|---|
| `W(t)` | WLAN 집계 DL 부하 | 12p_c `USER_DATA_USAGE_MEASURES`→`extract_wlan_dl_mbps`(`decide_wlan_gnb2_rule.py:173`); `data_analyzer.py:207`에서 오늘 급전 | 가용 |
| `\tilde C^w` | WLAN 잔여용량 | `max(Cw_total−W,0)` 엔진 `_observe` | 도출 |
| `λ_u, D̂_u` | per-UE 도착률·DL 지연 | 8p QOS_MONITORING per-SUPI `dlAveThroughput/dlPacketDelay`; 구독됨(`:298`, PER_FLOW·`incl_rat_type`). NF push + 신규 `extract_per_supi_qos` + `supi_map` 필요 | 개발필요 |
| `R_{g1}, R_{g2}` | per-UE 3GPP 도달레이트 | 13p_d `_RF_SIGNAL` RSRP/SINR→rate표; 구독됨(`:177`). NF push + SINR→Mbps 매핑; config `rbar` 폴백 | 개발필요 |
| `powerState` | 재시작 후 실제 gNB2 상태 | 13p_d `_POWER_ENERGY_CONSUMPTION`; RL 워크트리가 store에서 판독하는 선례(`_get_ricf_power_state`) | 개발필요 |
| `D^{max}_u` | per-UE 지연예산 | 9p/10p_a PERF_DATA `maxPdbDl`; 구독됨(`:421`). NF push + 추출기; config 폴백 | 개발필요 |
| `Q̂[(u,j)]` | per-UE·per-path 백로그 추정 | 엔진 합성: `λ_u·D̂_u·θ_last[u][j]`(Little). wire 필드 없음(설계상) | 도출 |
| `Z[u]` | 지연 가상큐 | 엔진 합성: `max(Z+λ_u(D̂_u−D^max_u),0)`, `NCOF_LYAPUNOV_STATE_PATH`로 영속 | 도출 |
| `V` | 에너지–지연 노브 | 엔진 파라미터; warm-start `V0=(A0−A1)/(B1−B0)`(§3) | 설정 |
| `ΔP_{g2}` | ACTIVE−DEEP_SLEEP 전력차 | 초기 config, 이후 13p_d 전력샘플 회귀 | 설정 |
| `κ^j, p_u^j, R̄_u^j` | CN 비트당 전력·tx 전력·기준레이트(`ê`용) | config dict(`κ` per access, `p_w=0`) | 설정 |
| `Cw_total, Λ, min_dwell_sec` | WLAN 용량·GBR 사다리·flap 가드 | config; 사다리 `{0,500,1000}`==`GBR_OFF/PARTIAL/HIGH`(`:93`); dwell은 베이스에 이미 존재(`gnb2_rule_engine.py:46`) | 설정 |
| `s → 15f` | ACTIVE/DEEP_SLEEP+RF 프리셋→RICF | `build_15f_cell_power(state,decision_iso,sub_id,corr_id)` 그대로 재사용(`:231`) | 가용 |
| `θ → 14_e` | 사다리 사영 `gbrDl/mbrDl`(WLAN·gNB2-NR set) | 신규 `_apply_qos_theta`가 `_is_wlan_set/_is_on_gnb`(`:318`) 재사용; **per-RAT만** — per-SUPI는 PCF 템플릿 변경 필요 | 가용 |

---

## 3. 알고리즘 & 정합성 노트

**핵심 수식**

$$\mu^{g1}_1=R^{g1}_1,\quad \mu^{g2}_2=s\,\sigma_2\,R^{g2}_2,\quad \mu^{w}_u=\tilde C^{w}/n^{w},\ \ \tilde C^{w}=C^{w}-W(t)$$

$$E=\underbrace{P^{g1}_{\mathrm{cst}}+s\,\Delta P^{g2}+\!\!\sum_u\!\sum_{j\in J_u\cap\{g1,g2\}}\!\!e^j_u d^j_u}_{E^{\mathrm{gNB}}}+\underbrace{P^{\mathrm{CN}}_0+\sum_u\sum_{j\in J_u}\kappa^j \nu^j_u}_{E^{\mathrm{CN}}},\quad \hat e^j_u=\frac{p^j_u}{\bar R^j_u}+\kappa^j\ (p^w_u{=}0)$$

**Wake-up test**(프레임 동결) / **연속 분할 LP**:

$$s^*=1 \iff \!\!\sum_{u:\,g2\in J_u}\!\!\big(Q^{g2}_u R^{g2}_u - V p^{g2}_u\big)^{+} + \delta_\theta > V\Delta P^{g2}\quad;\quad \min_{\theta_u\in\Delta^{J_u}} \sum_u \lambda_u \!\sum_{j\in J_u}\! \theta^j_u\big[Q^j_u + V\hat e^j_u\big]\ \ \text{s.t.}\ \sum_{u:w\in J_u}\!\lambda_u\theta^w_u\le\tilde C^w,\ \theta^{g2}_u\le\sigma_u$$

**성능 보장**: 임의 `V>0`에 모든 큐 mean-rate stable, `[O(1/V), O(V+T)]` 에너지–백로그 교환.

### 정합성 노트 (스펙 결함 4건 교정 — Fable 5 설계 + 검증)

1. **s 열거 ≡ wake-up test.** 둘 다 동일한 1-슬롯 drift-plus-penalty 상계를 최소화. `cost[1]−cost[0]=V·ΔP_g2 − [라우팅 relief]`이고, relief가 정확히 `Σ_u(Q_g2·R_g2−V·p_g2)⁺+δ_θ` — `(·)⁺`는 water-fill이 `Δ_2>0`일 때만 이동하므로 등장, `δ_θ`는 커플링 크레딧(gNB2 기상이 WLAN 용량을 풀어 UE1 비용까지 낮춤). 열거는 `δ_θ`를 **정확히** 재계산하므로 별도 추정 불요 → 더 견고. 비용 O(2·|U|log|U|), 60s에 자명하게 실시간. **주의**: step3 비용과 water-fill 목적함수는 **동일 `_pressure()`** 사용해야 함(안 그러면 argmin_s와 내부 θ*가 다른 목적함수로 계산됨).

2. **water-fill 정확성**(휴리스틱 아님). per-cycle 문제는 LP: per-UE 심플렉스 위 분리가능 선형목적 + **커플링 제약 1개**(WLAN 용량). `Δ_u=pressure[u][a(u)]−pressure[u][W]`, `Δ_u>0` 내림차순 greedy 충전이 표준 exchange argument로 최적, 기저해는 분수 UE **최대 1개**(n 심플렉스+1 용량 = n+1 tight). 2-UE에서 완전 정확.

3. **Z 가상큐 실사용화**(스펙 누락 교정). 스펙은 `Z[u]`를 유지하나 비용에 안 씀. Z를 두 경로에 **균일 가산**하면 `Δ_u`에서 상쇄되고 s 비교에서도 `λ_u·Z[u]`로 동일 → **no-op**. 충실한 DPP는 경로의 지연기여로 가중: `pressure(u,j) += Z[u]·λ_u/μ_j`(역서비스율, `μ_w=\tilde C_w`) → 지연위반 UE를 빠른 경로로 유도, WLAN 혼잡 시 wake 유인 정확히 상승.

4. **V0 warm-start 비순환화**(산술 교정). 스펙 `V0∼[…]/ΔP_g2`는 V가 양변에 있어 순환. 무차별 조건 `Q_{g2,2}R_{g2,2}−V·p_{g2,2}+δ_θ=V·ΔP_g2`를 풀면 **`V0=(Q_{g2,2}R_{g2,2}+δ_θ)/(ΔP_g2+p_{g2,2})`**(비순환, 분모에 `p_g2`). 라우팅 형식에선 두 비용곡선이 V에 affine `cost_s(V)=A_s+V·B_s` → **`V0=(A0−A1)/(B1−B0)`**(`A0>A1`이고 `B1>B0`일 때 유효), θ*(V) 때문에 조각-affine이라 1–2회 고정점 반복으로 수렴. `W=TH=500` 스냅샷에서 보정하면 Lyapunov 결정경계가 배포 TH 룰과 일치.

5. **사다리 사영**: θ를 RAT별 집계(`gbr_w←Σλ_uθ_w_u`, `gbr_g2←λ_2θ_g2_2`) 후 계획부하를 덮는 **최소 rung으로 올림(snap-up)** — gbrDl/mbrDl은 **admission cap**이라 올림이 배정을 조르지 않음, 오차 ≤500Mbps는 유계 교란(drift 상계의 O(1) 상수) → `[O(1/V),O(V+T)]` 유지. DEEP_SLEEP은 `gbr_g2=0`(=GBR_OFF). **주의**: TH 룰은 DEEP_SLEEP에서 WLAN=1000, 부하기반 snap은 500일 수 있음 → TH 등가 검증은 **15f 상태로 비교, 14_e rung은 제외**.

---

## 4. 엔진 설계 (`gnb2_lyapunov_engine.py`, drop-in)

> 실제 `generate_notification(...)` 계약에 맞춤(스펙의 가상 `on_notifications`가 아님). 2-UE 상태·s 열거·정확 water-fill·Z 역율가중·사다리 snap-up·상태 영속 포함. `decide_wlan_gnb2_rule.py`의 기존 헬퍼(`build_15f_cell_power`, `_is_wlan_set`, `_is_on_gnb`, `GNB2_VALUE`, `extract_wlan_dl_mbps`, `_parse_mbps`)를 재사용 — **전부 실존 심볼로 확인, 스켈레톤 문법 검증 통과**. 순수 파이썬(numpy 불요).

```python
"""Gnb2LyapunovEngine — Lyapunov drift-plus-penalty engine (2-UE, 2-access, shared WLAN).

Per 60s cycle minimizes  cost(s,theta) = V*s*dP_g2
    + sum_u lam_u * sum_{j in feas_u} theta[u][j] * pressure(u,j)
s.t. WLAN capacity (sum_u lam_u*theta_w_u <= Ctilde_w) and s=0 gating (UE2 -> WLAN only).
Same I/O contract as Gnb2RuleEngine. Pure Python (nncof-server has no numpy).
Activate: NCOF_DECISION_ENGINE=lyapunov
"""
from __future__ import annotations

import copy, json, logging, os
from datetime import datetime

from .gnb2_rule_engine import Gnb2RuleEngine
from .decide_wlan_gnb2_rule import (
    extract_wlan_dl_mbps, build_15f_cell_power, _parse_mbps,
    _is_wlan_set, _is_on_gnb, GNB2_VALUE,
)

logger = logging.getLogger(__name__)

UE1, UE2 = "ue1", "ue2"
W, G1, G2 = "w", "g1", "g2"
LADDER = (0.0, 500.0, 1000.0)  # == GBR_OFF/PARTIAL/HIGH rungs

DEFAULT_PARAMS = {
    "V": 100.0,                    # energy-delay knob; seed via warm_start_v0()
    "cw_total_mbps": 1000.0,
    "dp_g2_watt": 100.0,           # later: regression over 13p_d power samples
    "p_tx_watt": {G1: 20.0, G2: 20.0, W: 0.0},
    "rbar_mbps": {G1: 1000.0, G2: 1000.0, W: 1000.0},  # fallback if 13p_d absent
    "kappa": {G1: 0.02, G2: 0.02, W: 0.05},            # CN watt per Mbps
    "dmax_ms": {UE1: 100.0, UE2: 100.0},               # fallback if 9p absent
    "lam_mbps": {UE1: 250.0, UE2: 250.0},              # fallback if 8p absent
    "dhat_ms": {UE1: 50.0, UE2: 50.0},
    "supi_map": {},                # {"imsi-...01": "ue1", "imsi-...02": "ue2"}
}


def extract_per_supi_qos(notif_8p: dict | None) -> dict[str, dict]:
    """Per-SUPI dlPacketDelay/dlAveThroughput from an 8p QOS_MONITORING notification.
    (extract_wlan_dl_mbps sums SUPIs away — this keeps them.)"""
    out: dict[str, dict] = {}
    for item in (notif_8p or {}).get("notificationItems", []):
        supi = item.get("supi")
        if not supi:
            continue
        qm = item.get("qosMonitoringMeasurement") or item  # verify field vs stub
        out[supi] = {
            "dhat_ms": float(qm.get("dlPacketDelay") or 0.0),
            "lam_mbps": _parse_mbps(qm.get("dlAveThroughput")),
        }
    return out


def water_fill(feas, lam, pressure, cw_res):
    """EXACT optimum of: min sum_u lam_u sum_j theta[u][j]*pressure[u][j]
    s.t. sum_u lam_u*theta[u][W] <= cw_res, theta[u] in simplex over feas[u].
    One coupling constraint => greedy on pressure difference; <=1 fractional UE."""
    theta = {u: {j: 0.0 for j in paths} for u, paths in feas.items()}
    cap, elective = cw_res, []
    for u, paths in feas.items():
        if paths == (W,):            # s=0 gating: WLAN is UE2's only path
            theta[u][W] = 1.0
            cap -= lam[u]            # mandatory traffic consumes capacity first
        else:
            elective.append(u)
    cap = max(cap, 0.0)
    # Delta_u > 0 <=> own 3GPP path costlier than WLAN => u prefers WLAN
    elective.sort(key=lambda u: pressure[u][feas[u][0]] - pressure[u][W], reverse=True)
    for u in elective:
        alt = feas[u][0]
        if pressure[u][alt] - pressure[u][W] > 0.0 and cap > 0.0 and lam[u] > 0.0:
            frac = min(1.0, cap / lam[u])
            theta[u][W], theta[u][alt] = frac, 1.0 - frac
            cap -= frac * lam[u]
        else:
            theta[u][alt] = 1.0
    return theta


class Gnb2LyapunovEngine(Gnb2RuleEngine):
    ACCESS = {UE1: G1, UE2: G2}      # a(u): each UE's exclusive 3GPP access

    def __init__(self, min_dwell_sec: int = 0, params: dict | None = None):
        super().__init__(min_dwell_sec=min_dwell_sec)
        self.p = {**DEFAULT_PARAMS, **(params or {})}
        self.Q = {u: {j: 0.0 for j in (self.ACCESS[u], W)} for u in (UE1, UE2)}
        self.Z = {UE1: 0.0, UE2: 0.0}
        self.theta_last = {UE1: {G1: 1.0, W: 0.0}, UE2: {G2: 1.0, W: 0.0}}
        self.last_emitted_key = None  # WIDENED dedup key: (state, gbr_w, gbr_g2)
        self._state_path = os.getenv("NCOF_LYAPUNOV_STATE_PATH", "")
        self._load_state()            # DataAnalyzer.stop() re-creates the engine

    # ---- observation (target telemetry; config fallback per event family) ----

    def _observe(self, notif_12p_c, qos_monitoring, rf_signal, perf_data):
        w_mbps = extract_wlan_dl_mbps(notif_12p_c)          # 12p_c (wired today)
        obs = {"w_mbps": w_mbps,
               "cw_res": max(self.p["cw_total_mbps"] - w_mbps, 0.0),
               "lam": dict(self.p["lam_mbps"]), "dhat": dict(self.p["dhat_ms"]),
               "dmax": dict(self.p["dmax_ms"]), "rate": dict(self.p["rbar_mbps"]),
               "power_state": None}
        for supi, m in extract_per_supi_qos(qos_monitoring).items():    # 8p
            u = self.p["supi_map"].get(supi)
            if u:
                obs["lam"][u] = m["lam_mbps"] or obs["lam"][u]
                obs["dhat"][u] = m["dhat_ms"] or obs["dhat"][u]
        if rf_signal:                                                   # 13p_d
            obs["rate"].update(self._rates_from_rf(rf_signal))
            obs["power_state"] = self._power_state_from_rf(rf_signal)
        if perf_data:                                                   # 9p
            obs["dmax"].update(self._dmax_from_perf(perf_data))
        return obs

    def _rates_from_rf(self, n13) -> dict:   # TODO Phase 2: SINR/RSRP -> Mbps table
        return {}

    def _power_state_from_rf(self, n13):     # TODO Phase 2: restart recovery
        return None

    def _dmax_from_perf(self, n9) -> dict:   # TODO Phase 2: maxPdbDl per UE/5QI
        return {}

    # ---- Lyapunov state ----

    def _update_queues(self, obs):
        for u in (UE1, UE2):
            for j in self.Q[u]:  # Little's-law backlog, split by last routing
                self.Q[u][j] = obs["lam"][u] * (obs["dhat"][u] / 1e3) \
                    * self.theta_last[u].get(j, 0.0)
            self.Z[u] = max(
                self.Z[u] + obs["lam"][u] * (obs["dhat"][u] - obs["dmax"][u]) / 1e3, 0.0)

    def _ehat(self, j):          # per-bit RAN+CN power intensity; p_w = 0
        return self.p["p_tx_watt"][j] / max(self.p["rbar_mbps"][j], 1e-9) \
            + self.p["kappa"][j]

    def _pressure(self, u, j, obs):
        # Z weighted by inverse path service rate so the delay virtual queue
        # actually steers routing (a uniform +Z[u] would cancel in Delta_u AND
        # in the s-comparison — spec omission fixed here).
        mu = obs["cw_res"] if j == W else obs["rate"][j]
        return self.Q[u][j] + self.Z[u] * obs["lam"][u] / max(mu, 1e-9) \
            + self.p["V"] * self._ehat(j)

    # ---- decision: enumerate s; exact water-fill per s; same pressure both ----

    def _decide_lyapunov(self, obs):
        best = None
        for s in (0, 1):
            feas = {UE1: (G1, W), UE2: ((G2, W) if s == 1 else (W,))}
            pres = {u: {j: self._pressure(u, j, obs) for j in feas[u]} for u in feas}
            theta = water_fill(feas, obs["lam"], pres, obs["cw_res"])
            cost = self.p["V"] * s * self.p["dp_g2_watt"] + sum(
                obs["lam"][u] * sum(theta[u][j] * pres[u][j] for j in theta[u])
                for u in theta)
            if best is None or cost < best[0]:
                best = (cost, s, theta)
        _, s_star, theta_star = best
        return ("ACTIVE" if s_star else "DEEP_SLEEP"), theta_star

    def _project_ladder(self, theta, obs, state):
        def snap_up(x):  # gbr is an admission CAP: smallest rung >= planned load
            return next((r for r in LADDER if r >= x - 1e-9), LADDER[-1])
        gbr_w = snap_up(sum(obs["lam"][u] * theta[u].get(W, 0.0) for u in theta))
        gbr_g2 = snap_up(obs["lam"][UE2] * theta[UE2].get(G2, 0.0)) \
            if state == "ACTIVE" else 0.0
        return gbr_w, gbr_g2

    # ---- REAL I/O contract (caller: DataAnalyzer._analyze_and_generate) ----

    def generate_notification(
        self, notif_12p_c: dict, qos_template: list[dict], decision_iso: str,
        sub_id: str, corr_id: str | None, *,
        qos_monitoring: dict | None = None,   # 8p   (DataAnalyzer-assembled kwarg)
        rf_signal: dict | None = None,        # 13p_d
        perf_data: dict | None = None,        # 9p
        **_ignored,
    ):
        obs = self._observe(notif_12p_c, qos_monitoring, rf_signal, perf_data)
        if obs["w_mbps"] <= 0.0 and qos_monitoring is None:
            new_state, theta = "ACTIVE", self.theta_last   # missing-data guard
        else:
            self._update_queues(obs)
            new_state, theta = self._decide_lyapunov(obs)
        gbr_w, gbr_g2 = self._project_ladder(theta, obs, new_state)

        key = (new_state, gbr_w, gbr_g2)      # theta-only changes must not be lost
        if key == self.last_emitted_key:
            self._commit(theta)
            return None                       # emit-on-change
        if self.min_dwell_sec and self.last_change_at:
            elapsed = (datetime.fromisoformat(decision_iso)
                       - self.last_change_at).total_seconds()
            if elapsed < self.min_dwell_sec:
                self._commit(theta)
                return None
        self.last_emitted_key = key
        self.last_emitted_state = new_state   # keep base field coherent (NOT last_state)
        self.last_change_at = datetime.fromisoformat(decision_iso)
        self._commit(theta)
        return {
            "cell_power_15f": build_15f_cell_power(new_state, decision_iso,
                                                   sub_id, corr_id),
            "qos_policy_14e": self._apply_qos_theta(qos_template, gbr_w, gbr_g2),
        }

    def _apply_qos_theta(self, template, gbr_w, gbr_g2):
        out = copy.deepcopy(template)
        for top in out:
            for ev in top.get("eventNotifications", []):
                for info in ev.get("qosPolAssistInfos", []):
                    for assist in info.get("qosPolAssistInfo", []):
                        for ps in assist.get("qosPolAssistSets", []):
                            gbr = gbr_w if _is_wlan_set(ps) else (
                                gbr_g2 if _is_on_gnb(ps, GNB2_VALUE) else None)
                            if gbr is not None:
                                qps = ps.setdefault("qosParamSet", {})
                                qps["gbrDl"] = qps["mbrDl"] = f"{gbr} Mbps"
        return out

    # ---- persistence (survive create_decision_engine() re-creation) ----

    def _commit(self, theta):
        self.theta_last = theta
        self._save_state()

    def _save_state(self):
        if not self._state_path:
            return
        try:
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump({"Q": self.Q, "Z": self.Z, "theta_last": self.theta_last,
                           "last_emitted_key": self.last_emitted_key}, f)
        except OSError as e:
            logger.warning("lyapunov state save failed: %s", e)

    def _load_state(self):
        if not self._state_path or not os.path.exists(self._state_path):
            return
        try:
            with open(self._state_path, encoding="utf-8") as f:
                snap = json.load(f)
            self.Q, self.Z, self.theta_last = snap["Q"], snap["Z"], snap["theta_last"]
            key = snap.get("last_emitted_key")
            self.last_emitted_key = tuple(key) if key else None
            if key:
                self.last_emitted_state = key[0]
        except (OSError, ValueError, KeyError) as e:
            logger.warning("lyapunov state load failed: %s", e)


def warm_start_v0(engine: Gnb2LyapunovEngine, obs_at_th: dict) -> float:
    """TH<->V warm start, corrected & non-circular: cost_s(V) = A_s + V*B_s with
    A_s = sum_u lam*theta_s*(Q + Z-bias), B_s = s*dP_g2 + sum_u lam*theta_s*ehat.
    Indifference at the W=TH snapshot => V0 = (A0-A1)/(B1-B0); theta_s depends
    weakly on V via the water-fill, so run 1-2 fixed-point passes."""
    V0 = engine.p["V"]
    for _ in range(2):
        engine.p["V"] = V0
        ab = {}
        for s in (0, 1):
            feas = {UE1: (G1, W), UE2: ((G2, W) if s == 1 else (W,))}
            pres = {u: {j: engine._pressure(u, j, obs_at_th) for j in feas[u]}
                    for u in feas}
            th = water_fill(feas, obs_at_th["lam"], pres, obs_at_th["cw_res"])
            A = sum(obs_at_th["lam"][u] * sum(
                th[u][j] * (pres[u][j] - engine.p["V"] * engine._ehat(j))
                for j in th[u]) for u in th)
            B = s * engine.p["dp_g2_watt"] + sum(obs_at_th["lam"][u] * sum(
                th[u][j] * engine._ehat(j) for j in th[u]) for u in th)
            ab[s] = (A, B)
        num, den = ab[0][0] - ab[1][0], ab[1][1] - ab[0][1]
        if den <= 0 or num <= 0:
            break  # degenerate snapshot: waking is dominated (or free) — keep V
        V0 = num / den
    return V0
```

---

## 5. 아키텍처 삽입점 (3 additive diff)

전부 `prototype/nncof-server/src/nncof/core/` 내부, additive:

**(1) 팩토리 분기** — `gnb2_rl_engine.py:98-114` `create_decision_engine()`에 import 1 + elif 1(룰 폴백 전, RL 분기의 try/except 형태 미러):
```python
elif engine_kind == "lyapunov":
    try:
        return Gnb2LyapunovEngine(min_dwell_sec=min_dwell_sec)
    except Exception as e:
        logger.warning("Lyapunov 엔진 생성 실패(%s) — 룰 베이스로 폴백", e)
```
활성화: `NCOF_DECISION_ENGINE=lyapunov`.

**(2) 베이스 시그니처 확장** — `gnb2_rule_engine.py:31-38`에 keyword-only 파라미터 `*, qos_monitoring=None, rf_signal=None, perf_data=None` 추가(Rule/RL은 무시). **RL 워크트리 선례로 back-compat 검증됨**(`generate_notification(..., reported_power_state=None)` 추가·베이스 무시 — worktree `gnb2_rule_engine.py:42`). 런타임 호출은 앞 5개 인자를 **위치인자**로 넘기므로(`data_analyzer.py:207`) 공개 메서드명·위치계약 불변.

**(3) 텔레메트리 조립** — `data_analyzer.py`에 store-scan 헬퍼 3개(기존 `_get_wlan_performance_data:173` + 워크트리 `_get_ricf_power_state:194` 패턴): `_get_qos_monitoring()`(8p), `_get_rf_signal()`(13p_d), `_get_perf_data()`(9p) — `notif_data_store.get_all()` 순회(NF push 시 `notif_id`로 이미 적재). `:207` 호출부에 kwarg로 전달. per-SUPI 파싱은 엔진 `extract_per_supi_qos`에 두고 retrieval만 DataAnalyzer에 → 엔진은 store-agnostic·유닛테스트 가능.

> **"한 줄 교체" 판정**: 엔진 선택은 참(env + elif 1). Phase 1(W-only+config)은 diff (1)만으로 참. **full-telemetry 운용은 diff (2)+(3)(~50줄+kwarg 3개) 필요** — 오늘 `generate_notification`은 12p_c dict 하나만 받으므로 다중이벤트 경로가 없다. 구독/ingest/fan-out(`:217-230`) 변경 불요(DataAnalyzer는 결과의 `cell_power_15f/qos_policy_14e`만 읽음). `stop()` 엔진 재생성(`:95`)은 엔진 내부 `NCOF_LYAPUNOV_STATE_PATH` 스냅샷+13p_d powerState 재동기로 처리(DataAnalyzer 변경 불요).

---

## 6. 단계별 계획

| Phase | 목표 | 핵심 작업 | 종료 기준 |
|---|---|---|---|
| **0. 오프라인 검증 하네스** | 런타임 손대기 전 수학 증명(V0 TH-등가, V 스윕 단조성) | 독립 스크립트(`decide_wlan_gnb2_rule.py main()` 패턴)로 기록/샘플 12p_c JSON + 합성 8p/13p_d/9p를 엔진에 replay; `warm_start_v0` 구현; V 3-decade 스윕; 유닛테스트(water-fill LP 최적성 vs brute-force, s-enum vs 폐형 wake test, 사다리 snap-up, Z steering) | V=V0에서 방출 15f 상태가 모든 기록 트레이스에서 `decide_gnb2_state(W,500)`와 일치; V↑에 sleep 비율 단조증가; water-fill=brute-force 1e-9 일치(1000 랜덤) |
| **1. 런타임 엔진, W-only(오늘 배선)** | 12p_c + config 상수로 스택에 라이브, rule/rl 사용자 무영향 | `gnb2_lyapunov_engine.py` 추가; 팩토리 elif; `NCOF_LYAPUNOV_STATE_PATH` 스냅샷; cold-start 항상 발행·missing-data 강제 ACTIVE 가드; 현 HTTP/2(h2c) 스택에서 `NCOF_DECISION_ENGINE=lyapunov` 기동 | E2E 15f/14_e가 RICF/PCF mock에 60s 도달; 불변 `(state,gbr)` 키에 emit-on-change None; Q/Z가 `stop()`/재시작에 스냅샷 생존; rule/rl 회귀 무영향 |
| **2. full-telemetry 배선(본 계획의 개발 타깃)** | 8p/13p_d/9p populate+consume → per-UE 상태 실측화 | mock NF가 매 주기 QOS_MONITORING/_RF_SIGNAL/_POWER_ENERGY/PERF_DATA push(구독 존재); DataAnalyzer 3 헬퍼+`:207` kwarg; 베이스 시그니처 확장; `extract_per_supi_qos`(실 스텁 필드명 대조)·`_rates_from_rf`(합의 SINR→Mbps 표)·`_dmax_from_perf`·`_power_state_from_rf`; `supi_map` config; `ΔP_g2` 13p_d 회귀 | 엔진 로그가 per-UE λ/D̂/rate/D^max를 라이브 통지에서 소싱(정상상태 폴백 카운터 0); 재시작이 13p_d powerState로 s 재동기; 두 mock UE 비대칭 구동 시 per-UE Q/Z 정확히 분기 |
| **3. θ 액추에이션·튜닝** | 14_e에 연속-θ값 가시화, 에너지-지연 동작점 보정 | 확장된 dedup 키로 θ-only 변화 방출 확인; V 스윕 (에너지, 평균백로그, 지연위반율) 기록; flap 관찰 시 `min_dwell_sec=300`; per-SUPI 14_e `qosParamSet`을 PCF/두두원측과 추진(NCOF 밖 템플릿 변경) → 진짜 `σ_u` 액추에이션 | 측정 에너지-백로그 곡선이 `O(1/V)/O(V)` 형태; 선택 V가 D^max 위반예산 충족; 24h soak flap 無; per-SUPI 14_e 결정 문서화(채택 or 근거 있는 보류) |

---

## 7. 검증 (validation)

**TH 룰 등가(V0에서).** `W=500(=TH)` + λ/D̂/rate 명목 config로 스냅샷 고정, `warm_start_v0`로 V0 산출. 8p/9p/13p 부재(폴백 고정 → W만 움직이는 입력, 배포 룰과 동일한 1-D 특수형) 하에 기록 12p_c를 `decide_gnb2_state(W,500)`와 엔진(V=V0)에 replay → **15f 상태열 동일**해야 함(단 (a) Q/Z 정착 초기 몇 주기, (b) 14_e rung은 cap 의미차로 제외). 지속 불일치 = 잘못된 상수(ΔP_g2/κ/p_tx)이지 알고리즘 아님 → **파라미터 보정 겸용**.

**R1–R5 안전면 매핑**(룰은 자매 repo `ncof_yaml-main/tools/decide_cell_power.py` — 커버리지 주장 전 거기서 확인). R1(primary 상시)=모델 구조(gNB1은 ungated `P_cst`, `s`가 g1 미접촉 → 구조적으로 위반 불가, `feas[UE1]`이 g1 상실 안 함을 테스트로 assert). R3(wake 비용)=`V·s·ΔP_g2` 항(경계 양측 케이스로 검증). R4(spare capacity)=LP 제약 `Σλ_uθ_w_u≤\tilde C_w`(방출 배정이 `Cw_total−W` 초과 안 함). R5(QoS headroom)=mean-rate stability + `Z_u`(`D̂_u>D^max_u` 여러 주기 → Z 증가가 에너지상 sleep 선호에도 ACTIVE 강제). **R2는 자매 repo에서 읽어 매핑/제외 근거 명시**(열린 질문).

**수용 테스트**(결정적, 순수 파이썬, 스택 불요): (1) `V→대`: 안정 허용 시 sleep+offload(에너지 최소극한). (2) `V→0`: 양의 압력차면 wake(지연 최소극한). (3) 포화 `W≥Cw_total`⇒`cw_res=0`⇒s=0의 강제 WLAN 불가능⇒ACTIVE. (4) 여유 `W≈0`⇒DEEP_SLEEP+`θ_w_2=1`. (5) 데이터 없음⇒강제 ACTIVE(fail-safe). (6) cold start⇒첫 주기 발행. (7) dedup⇒동일 `(state,gbr_w,gbr_g2)` 연속⇒둘째 None. (8) dwell⇒`min_dwell_sec=300`이 60s 후 flip 억제하되 Q/Z/θ는 갱신(`_commit` 실행 확인). (9) 재시작⇒스냅샷 존재 시 Z≠0(지연 부채 보존), powerState 불일치 시 spurious emit 없이 재동기.

---

## 8. 리스크

- **8p/13p_d/9p 런타임 수신 미검증**: 구독은 있으나 mock NF가 실제 push하는지 미확인 → 안 오면 Phase 2가 NF측 개발에 블록되고 엔진은 조용히 config 상수로 동작(완화: 폴백사용 카운터 로그 + 지속 시 알람).
- **`notif_data_store`는 `notif_id`별 덮어쓰기·히스토리 없음**(`data_store.py:39`) → EWMA/큐추정용 시계열 못 줌 → 엔진이 자체 히스토리 유지, 주기 누락 시 직전 상태 재사용.
- **14_e per-RAT(per-SUPI 아님)**: per-UE `σ_u` 액추에이션은 NCOF 단독 불가 → PCF 템플릿 변경 전까지 2-UE 최적화가 RAT별 집계 cap으로만 실행되어 per-UE 이득 희석.
- **`stop()` 엔진 재생성**(`:95`): 스냅샷 파일 쓰기불가/손상 시 Q/Z 소거·Z 지연부채 손실 → 재축적까지 QoS 보호 저하.
- **파라미터 식별성**: `ΔP_g2/κ/p_tx`·SINR→rate 표가 wake 경계를 스케일 → 잘못된 상수가 유효 V를 배수로 이동 → 재보정마다 V0·V 스윕 재실행.
- **Little 큐 추정 지연**(D̂가 직전 주기 θ 반영) → 경계 근처 진동 가능(완화: `min_dwell_sec=300`, 확장 dedup 키, Z 역율 bias — soak 필수).
- **사다리 조밀도**: λ≈250Mbps/UE에서 50/50 분할이 0/500/1000로 snap → 실배정이 θ*와 최대 ~250Mbps 차이(유계이나 단기 에너지 수치에 가시).
- **`sub_id/corr_id`는 단일 구독에서**(`:212`) → 다중구독/다중셀 빌드는 id plumbing 필요(스펙 TODO).
- **`warm_start_v0` 퇴화**(den≤0 or num≤0): W=TH 스냅샷이 wake를 비용+relief로 만들지 않으면 → V0 신뢰 전 스냅샷 λ/Q sanity-check 필요.

---

## 9. 열린 질문 (파트너 협의)

- **kwarg vs store-handle**: 본 설계는 RL 워크트리 선례(DataAnalyzer-추출 kwarg, 엔진 store-agnostic)를 따름 — store를 엔진에 넘기는 방식(베이스 시그니처 변경 회피, 대신 store 내부 결합) 대비 팀 선호 확인.
- **8p 필드 shape**: `extract_per_supi_qos`가 `notificationItems[].supi` + `qosMonitoringMeasurement`류(dlPacketDelay/dlAveThroughput)를 가정 — Phase 2 전 실 생성 스텁(nupf/nef 모델) 대조 필수(현재 `NotificationItem.supi`만 확인, `notification_item.py:50`).
- **SUPI→UE 매핑**: static `supi_map` config인가, per-UE 구독필터에서 도출인가? 2-UE PoC에서 UE1/UE2 정체성 소유자?
- **SINR/RSRP→rate 표**: 누가 공급(두두원 측정 캠페인 vs 3GPP CQI 근사)? per-gNB인가 공유인가?
- **PCF/두두원이 per-SUPI 14_e `qosParamSet` 확장을 수용**해 `σ_u` 개별 액추에이션 가능? 아니면 Phase 3가 영구 per-RAT?
- **자매 repo `decide_cell_power.py`의 R2**가 스펙의 R1/R3/R4/R5 매핑에 없음 → 읽어서 DPP 면으로 매핑 or 제외 근거.
- **`δ_θ`**: 폐형 wake test는 문서용으로만(열거가 커플링을 정확 계산) vs 진단용 폐형 결정 매주기 로깅?
- **사다리 snap 의미**: snap-UP(cap≥계획부하, 본 설계) vs 최근접-rung(스펙 모호) — DEEP_SLEEP의 방출 14_e값(500 vs TH룰 1000)이 달라지므로 두두원과 확정.
- **V 단위·보고 규약**(현 정규화의 Mbit×Mbps/W) 고정 → 재보정 간 V0 비교가능.
- **8p `packetLossRate` 사용 여부**(스펙 IN에 있으나 알고리즘 미사용) — R_u 할인 or Z_u 가속자로?

---

## 10. 참고

- **출처 스펙**: `ETRI_두두원_수식화_간결버전.md`(정정판) · `ETRI_두두원_수식화_간결버전.pptx`(구판)
- **삽입 지점**: `prototype/nncof-server/src/nncof/core/{gnb2_rule_engine.py, gnb2_rl_engine.py(팩토리), decide_wlan_gnb2_rule.py(헬퍼), data_analyzer.py, subscription_request_builder.py, data_store.py}`
- **재사용 헬퍼(실존 확인)**: `build_15f_cell_power:231`, `apply_qos_policy:330`, `_is_wlan_set:318`, `_is_on_gnb:322`, `GNB2_VALUE:90`, `extract_wlan_dl_mbps:173`, `_parse_mbps:160` (모두 `decide_wlan_gnb2_rule.py`)
- **선례**: RL 워크트리 `rl-decision-engine-status-d5acbd`(generate_notification kwarg 추가·`_get_ricf_power_state` store 판독) — 개발 후 병합 대상
- **자매 룰/정식화**: `ncof_yaml-main/tools/{decide_wlan_gnb2_rule.py, decide_cell_power.py(R1-R5)}` · 이루온 DPP=고려대 곽정호팀 · 두두원 시나리오/PoC=ETRI 박세형
- **관련 문서**: `status.md`, 메모리 [[lyapunov-dpp-engine-plan]] · [[rl-closedloop-handoff]]
```
