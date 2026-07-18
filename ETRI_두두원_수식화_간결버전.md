# ETRI 두두원 수식화 — 간결버전 (구현 스펙)

> **목적**: 이 문서를 Claude Code에 넘겨 NCOF에 `Gnb2LyapunovEngine`(제3 엔진)을 구현한다.
> 기존 `Gnb2RuleEngine`(TH 룰)·`Gnb2RlEngine`과 **동일한 입출력 계약**을 유지하며, 규칙 기반 TH 결정을
> **Lyapunov drift-plus-penalty(DPP)** 정책으로 대체한다.
> 참조: `ncof_yaml-main/tools/decide_wlan_gnb2_rule.py`, `decide_cell_power.py`,
> `ncof_generated-main/prototype/nncof-server/src/nncof/core/gnb2_rule_engine.py`.

---

## 0. TL;DR — 무엇을 구현하나

- 매 **60초 사이클**마다 두 결정을 계산 → `15f`(cell power) + `14_e`(GBR/MBR) 발행:
  1. `s ∈ {0,1}` — gNB2 ACTIVE/DEEP_SLEEP
  2. `θ` — 각 UE 트래픽의 접속별 분할비 (GBR/MBR로 실행)
- 학습·신경망 없음. **큐·채널 인지 임계 + 연속 분할(water-filling)** = NumPy 수준 수십 줄.
- 기존 엔진과 **한 줄 교체**(`Gnb2RuleEngine` → `Gnb2LyapunovEngine`). SBI·주기·출력 포맷 그대로.
- 손잡이 하나 `V`로 "에너지 ↔ 지연"을 조절. `V→∞`면 에너지 최소, `V→0`면 지연 최소.

---

## 1. 토폴로지 & 표기 (정정된 실제 PoC)

```
UE1 ──▶ 3GPP gNB1 (상시 ON) ─┐
   └──▶ Non-3GPP WLAN ───────┼──▶ UPF/Anchor ──▶ DN/App
UE2 ──▶ 3GPP gNB2 (가변 s) ──┤
   └──▶ Non-3GPP WLAN ───────┘   (WLAN은 UE1·UE2 공유, UPF로 종단)
```

- **접속집합** `J_u`: `J₁ = {g1, w}`, `J₂ = {g2, w}`.
- gNB1 → UE1만, gNB2 → UE2만, WLAN → 두 UE 공유.
- **중요**: gNB2가 UE2 전용이므로 `s=0`이면 UE2는 3GPP 경로가 없어 **트래픽 전부 WLAN행**.

| 기호 | 의미 | 출처 |
|---|---|---|
| `u ∈ {1,2}` | UE / QoS flow | SUPI 매핑 |
| `j ∈ {g1,g2,w}` | 접속 | — |
| `A_u`, `λ_u` | 도착량·평균률 [Mbps] | 12p_c |
| `W(t)`, `C̃ʷ = Cʷ − W` | WLAN 배경부하 / 잔여용량 | 12p_c |
| `R^{g1}_1, R^{g2}_2` | 무선 속도 [Mbps] | 13p_d (RSRP/SINR) |
| `Q̂^j_u` | (추정) 큐 백로그 [bits or Mbps·s] | 추정(§6) |
| `Z_u` | 지연 가상큐 | 내부 상태 |
| `D̂_u`, `D^max_u` | 측정 지연 / 예산(maxPdbDl) | 8p / 9p·10p_a·11p_b |
| `s, σ_u, θ_u` | 결정변수 | 출력 |
| `V` | 에너지–지연 트레이드오프 노브 | 튜닝 |
| `ΔP^{g2}` | gNB2 ACTIVE−DEEP_SLEEP 전력차 | 13p_d 회귀 |
| `κ^j` | 접속별 CN(UPF) 비트당 전력 | CN 전력모델 |
| `Λ` | GBR/MBR 사다리 {0,500,1000} Mbps | config |

---

## 2. 결정 변수

- `s(n) ∈ {0,1}` : gNB2 ACTIVE(1) / DEEP_SLEEP(0). (gNB1은 상시 ON)
- `σ_u(n) ∈ {0,1}`, `σ_u ≤ s` : gNB2에서 UE `u`를 서빙할지 (PoC는 UE2만 해당).
- `θ_u(n) ∈ Δ^{J_u}` : UE `u`의 접속별 분할비.
  - UE1: `(θ^{g1}_1, θ^{w}_1)`, 합 = 1
  - UE2: `(θ^{g2}_2, θ^{w}_2)`, 합 = 1  (단 `s=0`이면 `θ^{g2}_2=0 ⇒ θ^{w}_2=1`)

---

## 3. 엔진 내부 상태 (사이클 간 유지)

```python
Qhat: dict[(u,j) -> float]   # 접속별 큐 추정
Z:    dict[u -> float]        # 지연 가상큐
last_emitted_state: "ACTIVE"|"DEEP_SLEEP"|None   # emit-on-change
last_change_at:     datetime|None                 # min-dwell 가드
```

---

## 4. 핵심 수식 (구현 참조)

**유도 서비스율** (고정 공유율):
$$\mu^{g1}_1=R^{g1}_1,\quad \mu^{g2}_2=s\,\sigma_2\,R^{g2}_2,\quad \mu^{w}_u=\frac{\tilde C^{w}}{n^{w}},\ \ \tilde C^{w}=C^{w}-W(t)$$

**s=0 결과 (게이팅)**:
$$s=0 \;\Rightarrow\; \mu^{g2}_2=0,\ \theta^{g2}_2=0 \;\Rightarrow\; \theta^{w}_2=1\quad(\text{UE2 전부 WLAN})$$

**교차도메인 에너지** (gNB + CN):
$$E=\underbrace{P^{g1}_{\mathrm{cst}}+s\,\Delta P^{g2}+\sum_u\!\!\sum_{j\in J_u\cap\{g1,g2\}}\!\!e^j_u d^j_u}_{E^{\mathrm{gNB}}}+\underbrace{P^{\mathrm{CN}}_0+\sum_u\sum_{j\in J_u}\kappa^j \nu^j_u}_{E^{\mathrm{CN}}},\quad e^j_u=\frac{p^j_u}{\bar R^j_u}$$

**비트당 총 강도**: $\hat e^j_u = p^j_u/\bar R^j_u + \kappa^j$ (단 $p^w_u=0$).

**gNB2 Wake-up test** (프레임 동결):
$$s^*=1 \iff \sum_{u:\,g2\in J_u}\big(Q^{g2}_u R^{g2}_u - V p^{g2}_u\big)^{+} + \delta_\theta > V\,\Delta P^{g2}\qquad[\text{PoC: }u=2]$$

**연속 분할 LP (water-filling)** — 매 사이클, 프레임 동결 가중치:
$$\min_{\theta_u\in\Delta^{J_u}} \sum_u \lambda_u \!\sum_{j\in J_u}\! \theta^j_u\big[Q^j_u + V\hat e^j_u\big]\quad\text{s.t.}\ \sum_{u:\,w\in J_u}\!\lambda_u\theta^w_u \le \tilde C^w,\ \ \theta^{g2}_u\le\sigma_u$$
- 해: UE를 **압력차** $\Delta_u=[Q^{a(u)}_u+V\hat e^{a(u)}_u]-[Q^{w}_u+V\hat e^{w}_u]$ 내림차순 정렬 후
  ($a(1)=g1,\ a(2)=g2$) `Δ_u>0`인 UE부터 WLAN을 greedy 충전, 잔여 소진 지점의 한 UE만 분수 분할.

**성능 보장**: 임의의 `V>0`에 대해 모든 큐 mean-rate stable, `[O(1/V), O(V+T)]` 에너지–백로그 트레이드오프.

---

## 5. 알고리즘 (per-cycle) — 구현 대상

`s∈{0,1}`를 **열거**하고 각각 water-filling을 풀어 총비용이 작은 쪽을 고른다 (wake-up test와 동치, 구현이 견고).

```
INPUT : 통지(12p_c[필수], 8p, 13p_d, 9p/10p_a), 파라미터 V, Λ, ΔP^{g2}, κ, min_dwell
STATE : Qhat, Z, last_emitted_state, last_change_at

1. 관측
   W      ← Σ dlAverageThroughput  (12p_c)         # WLAN 배경부하 proxy
   Cw_res ← max(Cw_total − W, 0)                    # WLAN 잔여용량
   R_g1_1, R_g2_2 ← 13p_d RSRP/SINR → 링크적응표     # 없으면 config 상수
   Dhat_u ← 8p dlPacketDelay ; lam_u ← 8p/12p_c dlAveThroughput

2. 큐 상태 갱신 (직접 텔레메트리 없으면 Little/가상큐)
   for u,j:  Qhat[u,j] ← estimate_backlog(...)      # 기본: lam_u * Dhat_u 배분
   for u:    Z[u] ← max(Z[u] + lam_u*(Dhat_u − Dmax_u), 0)

3. s 열거
   for s in (0,1):
       feasible_u = {UE1:{g1,w}, UE2:({g2,w} if s==1 else {w})}   # ← sgate
       theta[s]   = water_fill(feasible_u, Qhat, ehat, lam, Cw_res, V)
       cost[s]    = V*s*ΔP^{g2} + Σ_u lam_u * Σ_{j∈feasible} theta[s][u,j]*(Qhat[u,j] + V*ehat[u,j])
   s* = argmin_s cost[s] ;  theta* = theta[s*]
   # (min-dwell 가드: 직전 변경 후 min_dwell 미만이면 s 유지)

4. 사다리 사영 + 발행
   state  = "ACTIVE" if s*==1 else "DEEP_SLEEP"
   gbr    = project_theta_to_ladder(theta*, Λ)      # {0,500,1000}
   if state == last_emitted_state:  return None       # emit-on-change
   return { cell_power_15f: build_15f(state, ...),
            qos_policy_14e: build_14e(gbr, ...),
            change_indicator: True }
```

`water_fill` (2-UE 명시형):

```
def water_fill(feasible, Q, e, lam, Cw_res, V):
    theta = {}
    # 각 UE의 3GPP 대안이 없으면(=UE2 & s=0) WLAN 강제
    forced_w = [u for u in UEs if feasible[u] == {"w"}]
    # 압력차 Δ_u (양수 = WLAN이 유리) — 3GPP 대안이 있는 UE만
    cand = [u for u in UEs if "w" in feasible[u] and len(feasible[u]) > 1]
    a = {1:"g1", 2:"g2"}
    delta = {u: (Q[u,a[u]] + V*e[u,a[u]]) - (Q[u,"w"] + V*e[u,"w"]) for u in cand}
    cap = Cw_res
    # 강제 WLAN UE 먼저 용량 차감
    for u in forced_w:
        theta[u,"w"] = 1.0; cap -= lam[u]
    # 압력차 큰 순서로 greedy 충전
    for u in sorted(cand, key=lambda u: delta[u], reverse=True):
        if delta[u] <= 0 or cap <= 0:
            theta[u,a[u]] = 1.0; theta[u,"w"] = 0.0           # 3GPP로
        else:
            move = min(lam[u], cap)
            theta[u,"w"] = move/lam[u]; theta[u,a[u]] = 1 - theta[u,"w"]
            cap -= move
    return theta
```

---

## 6. Python 스켈레톤 (drop-in, `Gnb2RuleEngine` 시그니처 정합)

```python
# ncof/core/gnb2_lyapunov_engine.py  (신규)
from datetime import datetime
# 기존 헬퍼 재사용: build_15f_cell_power, apply_qos_policy, CELL_POWER_PRESETS
from .decide_wlan_gnb2_rule import build_15f_cell_power, apply_qos_policy

UES = [1, 2]
ACCESS = {1: ["g1", "w"], 2: ["g2", "w"]}   # J_u
PRIMARY_3GPP = {1: "g1", 2: "g2"}

class Gnb2LyapunovEngine:
    """규칙 엔진과 동일 I/O. TH 대신 Lyapunov DPP로 (s, θ) 결정."""
    def __init__(self, V=100.0, Cw_total_mbps=1000.0, dP_g2=1.0,
                 kappa=None, p=None, R_nominal=None, ladder=(0.0, 500.0, 1000.0),
                 min_dwell_sec=0):
        self.V = V
        self.Cw_total = Cw_total_mbps
        self.dP_g2 = dP_g2                       # ACTIVE−DEEP_SLEEP 전력차
        self.kappa = kappa or {"g1":0.0,"g2":0.0,"w":0.0}   # CN 비트당(측정 보정)
        self.p = p or {"g1":1.0,"g2":1.0,"w":0.0}           # 전송전력(측정 보정)
        self.R_nom = R_nominal or {"g1":1000.0,"g2":1000.0,"w":1000.0}
        self.ladder = ladder
        self.min_dwell_sec = min_dwell_sec
        # 내부 상태
        self.Qhat = {(u,j):0.0 for u in UES for j in ACCESS[u]}
        self.Z = {u:0.0 for u in UES}
        self.last_state = None
        self.last_change_at = None

    # ---- 1. 관측 ----
    def _observe(self, n12, n8=None, n13=None):
        W = self._sum_wlan_dl(n12)               # TODO: 기존 extract_wlan_dl_mbps 재사용
        Cw_res = max(self.Cw_total - W, 0.0)
        R = {"g1": self._rate(n13, "000001"),    # TODO: 13p_d RSRP/SINR → rate
             "g2": self._rate(n13, "000002")}
        lam, Dhat = self._per_ue_qos(n8)         # TODO: 8p dlAveThroughput/dlPacketDelay
        Dmax = self._budgets()                   # TODO: 9p/10p_a maxPdbDl
        return W, Cw_res, R, lam, Dhat, Dmax

    # ---- 2. 큐 추정 (Little / 가상큐) ----
    def _update_queues(self, lam, Dhat, Dmax):
        for u in UES:
            for j in ACCESS[u]:
                # 기본: per-UE 지연×도착률을 접속에 배분(균등 or 측정 기반). 필요시 교체.
                self.Qhat[(u,j)] = max(lam.get(u,0.0) * Dhat.get(u,0.0), 0.0)
            self.Z[u] = max(self.Z[u] + lam.get(u,0.0)*(Dhat.get(u,0.0) - Dmax.get(u,0.0)), 0.0)

    def _ehat(self, j):   # 비트당 총(RAN+CN) 강도
        return self.p[j] / max(self.R_nom[j], 1e-9) + self.kappa[j]

    # ---- 3. s 열거 + water-filling ----
    def _decide(self, Cw_res, R, lam):
        best = None
        for s in (0, 1):
            feas = {u: (ACCESS[u] if not (u==2 and s==0) else ["w"]) for u in UES}
            theta = self._water_fill(feas, lam, Cw_res)
            cost = self.V * s * self.dP_g2
            for u in UES:
                for j in feas[u]:
                    w = self.Qhat[(u,j)] + self.V * self._ehat(j)
                    cost += lam.get(u,0.0) * theta[(u,j)] * w
            if best is None or cost < best[0]:
                best = (cost, s, theta)
        return best[1], best[2]          # s*, theta*

    def _water_fill(self, feas, lam, Cw_res):
        theta = {(u,j):0.0 for u in UES for j in feas[u]}
        forced = [u for u in UES if feas[u] == ["w"]]
        cand   = [u for u in UES if "w" in feas[u] and len(feas[u]) > 1]
        a = PRIMARY_3GPP
        cap = Cw_res
        for u in forced:
            theta[(u,"w")] = 1.0; cap -= lam.get(u,0.0)
        delta = {u: (self.Qhat[(u,a[u])] + self.V*self._ehat(a[u]))
                    - (self.Qhat[(u,"w")]  + self.V*self._ehat("w")) for u in cand}
        for u in sorted(cand, key=lambda u: delta[u], reverse=True):
            if delta[u] <= 0 or cap <= 0:
                theta[(u,a[u])] = 1.0
            else:
                move = min(lam.get(u,0.0), cap)
                fw = move / max(lam.get(u,1e-9), 1e-9)
                theta[(u,"w")] = fw; theta[(u,a[u])] = 1.0 - fw; cap -= move
        return theta

    # ---- 4. 사다리 사영 + 발행 (emit-on-change, min-dwell) ----
    def on_notifications(self, n12, n8=None, n13=None, decision_iso=None):
        W, Cw_res, R, lam, Dhat, Dmax = self._observe(n12, n8, n13)
        self._update_queues(lam, Dhat, Dmax)
        s, theta = self._decide(Cw_res, R, lam)
        state = "ACTIVE" if s == 1 else "DEEP_SLEEP"

        now = datetime.fromisoformat(decision_iso) if decision_iso else datetime.now()
        if state == self.last_state:
            return None                                   # emit-on-change
        if self.min_dwell_sec and self.last_change_at and \
           (now - self.last_change_at).total_seconds() < self.min_dwell_sec:
            return None                                   # min-dwell 가드
        self.last_state, self.last_change_at = state, now

        gbr = self._project_gbr(theta, state)             # {gNB2, WLAN} GBR/MBR (사다리)
        return {
            "cell_power_15f": build_15f_cell_power(state, decision_iso, ...),  # TODO ids
            "qos_policy_14e": apply_qos_policy(qos_template, state),           # 또는 gbr로 커스텀
            "change_indicator": True,
        }

    def _project_gbr(self, theta, state):
        # θ(연속) → 사다리 Λ={0,500,1000}. PoC 2-UE:
        #   WLAN GBR ≈ project( θ^w_2 * 1000 ),  gNB2 GBR ≈ project( θ^{g2}_2 * 1000 )
        def proj(x): return min(self.ladder, key=lambda L: abs(L - x))
        return {"wlan": proj(theta.get((2,"w"),1.0)*1000.0),
                "gnb2": proj(theta.get((2,"g2"),0.0)*1000.0)}
    # _sum_wlan_dl / _rate / _per_ue_qos / _budgets / _project_gbr 는 repo 파서로 채운다.
```

> **엔진 교체 지점**: `gnb2_rule_engine.py`의 `Gnb2RuleEngine`를 사용하는 곳에서
> `Gnb2LyapunovEngine(V=...)`로 인스턴스만 바꾸면 됨. `on_notifications(...)` 반환 계약 동일.

---

## 7. SBI 입출력 계약

**입력**
- `12p_c` (UPF→NCOF, `USER_DATA_USAGE_MEASURES`): `dlAverageThroughput` 합 → `W(t)` [필수]
- `8p` (QoS_MONITORING): SUPI별 `dlPacketDelay`, `dlAveThroughput`, `_packetLossRate` → `Dhat_u, lam_u`
- `13p_d` (`_RF_SIGNAL`/`_POWER_ENERGY_CONSUMPTION`): RSRP/SINR → `R^{g2}`, powerState 동기(재시작 복구)
- `9p/10p_a/11p_b` (PERF_DATA): `maxPdbDl` → `Dmax_u`

**출력**
- `15f` (NCOF→RICF): gNB2 `_cellPowerState` = `ACTIVE|DEEP_SLEEP` (+RF preset). ← `s`
- `14_e` (NCOF→PCF): `qosParamSet.gbrDl/mbrDl` (WLAN·gNB2-NR set). ← `θ` 사다리 사영

---

## 8. 파라미터 · 튜닝

| 이름 | 기본 | 의미 |
|---|---|---|
| `V` | (보정) | 에너지–지연 노브. ↑=에너지 우선, ↓=지연 우선 |
| `Cw_total` | 1000 Mbps | WLAN 총용량 (AP 포화 테스트로 보정) |
| `dP_g2` | (측정) | gNB2 ACTIVE−DEEP_SLEEP 전력차 (13p_d 회귀) |
| `kappa[j]` | (측정) | 접속별 CN 비트당 전력 |
| `Λ` | {0,500,1000} | GBR/MBR 사다리 |
| `min_dwell_sec` | 0 | flap 방지 가드(관찰 시 300) |

**TH ↔ V warm-start**: 현행 TH=500 Mbps 운용점과 동일 거동을 주는 `V₀`에서 시작해 스윕.
$$V_0 \approx \frac{\big[\sum_u (Q^{g2}_u R^{g2}_u - Vp^{g2}_u)^+ + \delta_\theta\big]\big|_{W=\mathrm{TH}}}{\Delta P^{g2}}$$

---

## 9. 엣지 케이스 & 정합성 (구현 시 체크)

- **`s=0` ⇒ UE2 전부 WLAN** (`θ^w_2=1`): `_decide`의 `feas`에서 g2 제거로 강제됨. 반드시 유지.
- **WLAN 데이터 없음/`W=0`**: `Cw_res` 과대평가 위험 → cold-start 또는 missing-data 가드(강제 ACTIVE) 권장 (기존 룰 §9와 동일).
- **cold start** (`last_state=None`): 첫 사이클은 무조건 발행.
- **재시작 복구**: `13p_d` powerState로 `last_state` 동기 (= 규칙 R2).
- **사다리 사영 오차**: 유계 → 이론 보장의 차수 불변(상수만 이동).
- **`emit-on-change`**: 상태 불변 시 `None` 반환(통지 폭주 방지).

---

## 10. 기존 룰과의 관계 (검증 기준)

- 배포 TH 룰 = Wake-up test를 **W(t) 1차원으로 축약**한 특수형 → `V₀`에서 두 엔진 결정이 일치해야 함(회귀 테스트).
- `decide_cell_power.py`의 R1–R5 = DPP 최적 정책의 **안전 면**:
  - R1(primary 상시) = 모델 구조(gNB1 비게이팅), R3 = `V·ΔP^{g2}` 항,
    R4(spare capacity) = LP 용량 제약 `Σλ_u θ^w_u ≤ C̃^w`, R5(QoS headroom) = 안정성+가상큐 `Z_u`.
- **수용 테스트 아이디어**: 동일 통지 스트림에서 (a) `V→∞`면 에너지 최소·백로그 최대, (b) `V→0`이면 반대,
  (c) WLAN 포화 레짐에서 gNB2가 자동 ACTIVE로 전환, (d) 여유 레짐에서 DEEP_SLEEP + WLAN offload 확대.

---

*근거 파일: `두두원_시나리오.pdf`, `이루온_시나리오.png`, `고려대 학술용역_이루온_수식화.pdf`,
`ncof_yaml-main/tools/decide_wlan_gnb2_rule.py` · `decide_cell_power.py` · `scenario_wlan_gnb2_rule.md`.
자매 정식화(이루온): 고려대 곽정호 교수팀. 두두원 시나리오·PoC 설계: ETRI 박세형.*
