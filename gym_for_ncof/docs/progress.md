# gNB#2 에너지 모델 (branch: `gnb_energy`) — 진행 상황 & 다음 작업

> 목적: 3GPP **TR 38.864** BS 전력 소비 모델을 NCOF의 **gNB#2 sleep/active 결정**에 적용하고,
> 룰 베이스를 RL(PPO)로 대체한다. gNB#2는 **DEEP_SLEEP / ACTIVE 2-state만** 사용.

작성: 2026-06-26 · 작성자 핸드오프용 (다음 세션에서 이어서 진행)

---

## 0. 한눈에 — 상태 요약

| 단계 | 내용 | 상태 |
|---|---|---|
| Stage 1 | RL 보상을 38.864 상대전력으로 정렬 (env) | ✅ 완료 |
| Stage 1 | w_q 스윕 + mixed 트래픽 학습 → 정책 확정 | ✅ 완료 |
| Stage 2 (a) | mock RICF 13p_d 피드백을 2-state로 정렬 | ✅ 완료 |
| **Stage 2 (b)** | **전이 연출(cosmetic) — 상태전환 직후 1회 표식** | ⬜ TODO |
| **Stage 2 (c)** | **13p_d 전력 피드백을 RL 관측으로 되먹임 (폐루프)** | ⬜ TODO (본체) |

브랜치 `gnb_energy` 커밋 (origin 동기화됨):
- `22dc713` Stage 1: 38.864 보상 정렬 (env.py) + 계획 pptx
- `3f5ebc5` w_q 스윕 + mixed 트래픽 학습 (sweep_wq.py, traffic.py, train.py, 정책)
- `08edb51` Stage 2(a): mock RICF 13p_d 2-state 피드백

---

## 1. 사용하는 38.864 값 (BS Category 1, Set 1)

| 기호 | 의미 | 값 | 출처 |
|---|---|---|---|
| P(ACTIVE) | 상대전력 | **280** | Table 5.1-3 |
| P(DEEP_SLEEP) | 상대전력 | **1** (기준) | Table 5.1-3 |
| E(deep sleep) | 전이에너지 | **1000 rel·ms = 1 rel·s** | Table 5.1-5 |
| T(deep sleep) | 전이시간 | **50 ms** | Table 5.1-4 |

- 모두 **상대값**(deep sleep=1 기준), 절대 W 아님 — RL 보상엔 상대값으로 충분.
- 에너지 = 상대전력 × 시간. (예: ACTIVE 1분 = 280×60 = 16,800 rel·s / DEEP 1분 = 60)
- 원본 스펙: `38864-i10.pdf` (repo 루트), 상세 계획: `gym_for_ncof/docs/NCOF_gNB2_energy_model_plan.pptx`

---

## 2. 완료된 것 (참고용 상세)

### Stage 1 — RL 보상 (`gym_for_ncof/src/gym_for_ncof/env.py`)
- 상수: `P_ACTIVE=280`, `P_DEEP_SLEEP=1`, `E_TRANSITION_REL_S=1.0`
- config 손잡이: `energy_weight`(w_e=1), `qos_weight`(w_q=5), `switch_cost`(w_s=0.05),
  `p_active`, `p_deep_sleep`, `e_transition_rel_s`
- 보상(스텝당, P_ACTIVE로 정규화 → [0,1]):
  ```
  r = -( w_e·P(state)/280  +  w_q·max(0, wlan+gnb2_load-capacity)/100  +  w_s·switch
         +  w_e·E/280 (active→deep 진입 시 1회) )
  ```
- 관측 계약 **불변** → export된 정책 JSON이 prototype `Gnb2RLEngine`과 호환 (nncof-server 변경 불필요).

### w_q 스윕 결과 (`scripts/sweep_wq.py`)
- **절벽(cliff)**: w_q ≤ 2 → 무조건 sleep → QoS 위반 ~40%. w_q ≥ 3 → 위반 0.
- 안전 구간(≥3)에선 active 비율(에너지)이 w_q와 무관하게 ~0.5 (트래픽이 정하는 물리 한계).
- **결정: w_q = 5** (절벽 위 마진 + 에너지 최저급). env 기본값 그대로.

### mixed 트래픽 (`traffic.py`, `train.py`)
- `traffic_mode="mixed"`: 에피소드마다 markov/toggle/sine 무작위 → sine OOD 불안정 해소.
- `train.py`의 `ENV_CONFIG["traffic_mode"]="mixed"`.

### 최종 정책 평가 (w_q=5, mixed, PPO 50 iter)
| mode | RL active | RL 위반 | 룰 active | 룰 위반 |
|---|---|---|---|---|
| markov | 0.505 | 0.000 | 0.438 | 0.017 |
| toggle | 0.500 | 0.000 | 0.500 | 0.000 (룰 100% 일치) |
| sine | 0.414 | 0.006 | 0.387 | 0.014 |
- always-active 대비 **약 44% 에너지 절감**, QoS 위반 ≈ 0.

### Stage 2(a) — mock RICF 13p_d 2-state 피드백 (`prototype/nnef-server/src/nnef/impl/simulation.py`)
- 이전: `power_state`를 6개 랜덤(MICRO_SLEEP/ACTIVE_DL/…) → RICF→NCOF 통지에 6-state 노출.
- 이후: 모든 `_POWER_ENERGY_CONSUMPTION` info가 **NCOF가 명령한 상태**(`NCOFEventNotificationImpl.cell_power_state`,
  없으면 ACTIVE)만 보고. 전력값 38.864(ACTIVE=280/DEEP=1), energy=P×60.
- 새 헬퍼: `_power_energy_for_state(state)` + `_REL_POWER` dict.

---

## 3. ⬜ TODO (b) — 전이 연출 (cosmetic, 우선순위 낮음)

**왜 낮은가**: 통지 주기(~6s) ≫ 전이시간(50ms)이라, literal 50ms 지연은 화면상 no-op
(다음 주기에 이미 새 상태로 보임). 그래서 T=50ms는 "모델 파라미터로 문서화"만 하고 미구현.

**(b)를 굳이 한다면 — 발표 연출용**:
- 상태 변경 **직후 첫 통지 1회**에만 `power_state`를 `"TRANSITIONING"`(또는 직전 상태 유지)으로 표시,
  또는 그 사이클 13p_d에 전이에너지 E를 표기해 "전이 중"을 보여줌.
- 위치: `prototype/nnef-server/src/nnef/impl/simulation.py`의 `periodic_notification_sender`
  내 2-state 반영 블록. 직전 상태를 모듈/클래스 변수로 들고 비교해 "변경된 첫 사이클" 판별.
- ⚠️ 물리적 50ms가 아니라 **시연용 표식**임을 명확히. NCOF 결정엔 영향 없게.

---

## 4. ⬜ TODO (c) — 13p_d 전력 피드백을 RL 관측으로 되먹임 (Stage 2 본체)

**목표**: 현재 RL 관측의 `gnb2_active`는 **NCOF 자신의 기억**(`last_emitted_state`)에서 옴.
이를 **RICF가 실제로 보고한 13p_d 전력상태**(실제 적용 결과)로 바꿔 **폐루프**를 만든다.

### 현재 상태 (확인됨)
- NCOF는 **13p_d 전력상태를 결정에 쓰지 않음** (grep 결과 nncof 코어에 power_state 파싱 없음).
- 관측 생성: `prototype/nncof-server/src/nncof/core/gnb2_rl_engine.py` `_build_obs()`
  ```
  obs = [wlan_dl_norm, prev_wlan_dl_norm, gnb2_active]
  gnb2_active = 1.0 if self.last_emitted_state == "ACTIVE" else 0.0   # ← NCOF 기억
  ```
- 알림 수신/분석 경로: `core/data_analyzer.py`, `core/subscription_handler.py`,
  알림 콜백은 `apis/nef_events_notifications_*` → handler 저장 (`core/data_store.py`).

### 구현 단계 (제안)
1. **NCOF에서 RICF 13p_d 파싱**: RICF(nnef RICF모드)가 보내는 `_POWER_ENERGY_CONSUMPTION`의
   `power_state`(ACTIVE/DEEP_SLEEP)를 수신 경로에서 추출해 핸들러/data_store에 보관.
   (gNB#2 식별: `_loc...globalGnbId.gNbId.gNBValue == "000002"`)
2. **관측에 반영**: `gnb2_rl_engine._build_obs()`의 `gnb2_active`를 `last_emitted_state` 대신
   **RICF가 보고한 실제 상태**로 교체(또는 피처 추가). 전이 중에는 명령≠실제일 수 있음.
3. ⚠️ **관측 차원/계약이 바뀌면**: `OBS_FEATURES`(env.py)·`policy_export`·정책 JSON이 모두 영향.
   - 피처를 **교체**(차원 동일)면 재학습만 하면 됨 (export 포맷 불변).
   - 피처를 **추가**(차원 증가)면 env 관측공간 + `_build_obs` + 재학습 + 재export 모두 갱신.
   - gym env(`env.py`)에도 동일한 "실제 상태" 신호를 시뮬레이션해 넣어야 학습/추론 관측이 일치.
4. **재학습 → 재export → 검증** (아래 5절 명령).

### 주의 / 설계 메모
- 현재 cadence(결정 60s)에선 명령상태 == 실제상태라 **행동 변화는 미미**, (c)는 주로
  **아키텍처 현실성**(실제 적용 결과 기반 결정)을 위한 것. 빠른 cadence/RL 고도화 때 가치↑.
- 폐루프가 생기면 "내가 보낸 action이 실제로 적용됐는지"를 reward/관측에 반영 가능 →
  실 환경과의 격차 축소 (todo_table.md의 RL observation 확장과 연결).

---

## 5. 실행 / 검증 방법

```bash
# RL 학습 (gym_for_ncof/ 에서)
cd gym_for_ncof
uv sync
uv run python scripts/train.py --iters 50      # → models/gnb2_policy.json
uv run python scripts/evaluate.py --episodes 20 # RL vs 룰(500) 비교
uv run python scripts/sweep_wq.py               # w_q 스윕 재확인

# prototype에서 RL 엔진으로 NCOF 실행
cd prototype/nncof-server
NCOF_DECISION_ENGINE=rl sh run.sh               # 기본은 rule; rl이면 정책 JSON 로드
#   정책 경로 기본값: <repo>/gym_for_ncof/models/gnb2_policy.json
#   NCOF_RL_POLICY_PATH 로 override 가능, 로드 실패 시 룰 베이스로 자동 폴백

# mock RICF (13p_d 2-state 피드백 확인용)
cd prototype/nnef-server && sh run_ricf.sh       # 포트 8003
```

데모 포트: NCOF 8000 / SMF 8001 / NEF(AF) 8002 / RICF 8003 / PCF(callback) 8004 / UI 5173.

---

## 6. 핵심 파일 지도

| 파일 | 역할 |
|---|---|
| `gym_for_ncof/src/gym_for_ncof/env.py` | RL 환경 + 38.864 보상 (P/280, E, w_e/w_q/w_s) |
| `gym_for_ncof/src/gym_for_ncof/traffic.py` | 트래픽 생성기 (markov/toggle/sine/**mixed**) |
| `gym_for_ncof/src/gym_for_ncof/policy_export.py` | torch→JSON export + 순수파이썬 추론 (포맷 `ncof-gnb2-mlp-v1`) |
| `gym_for_ncof/scripts/train.py` | PPO 학습 → 정책 JSON |
| `gym_for_ncof/scripts/sweep_wq.py` | w_q 스윕 |
| `gym_for_ncof/scripts/evaluate.py` | RL vs 룰 평가 |
| `gym_for_ncof/models/gnb2_policy.json` | 학습 산출 정책 (prototype이 읽음) |
| `prototype/nncof-server/src/nncof/core/gnb2_rl_engine.py` | RL 추론 엔진(_build_obs) + create_decision_engine |
| `prototype/nncof-server/src/nncof/core/gnb2_rule_engine.py` | 룰 베이스(_decide 훅, emit-on-change/dwell) |
| `prototype/nncof-server/src/nncof/core/decide_wlan_gnb2_rule.py` | 12p_c 추출, 임계 판정, 15f/14_e 생성 |
| `prototype/nncof-server/src/nncof/core/data_analyzer.py` | 주기적 분석 경로 ((c)에서 13p_d 파싱 후보) |
| `prototype/nnef-server/src/nnef/impl/simulation.py` | mock RICF 13p_d 피드백 (Stage 2a 적용됨) / NCOFEventNotificationImpl.cell_power_state |

---

## 7. 다음 세션 시작 체크리스트
1. `git checkout gnb_energy` (이미 origin에 푸시됨, 최신 `08edb51`).
2. 이 문서 3절(b) / 4절(c) 중 선택. 권장: **(c) 폐루프**부터 (본체), (b)는 발표 직전 연출로.
3. (c) 착수 시 4절 "구현 단계" 따라가되, **관측 차원 변경 여부**를 먼저 결정 (교체 vs 추가).
4. 변경 후 항상: 재학습 → `evaluate.py`로 QoS 위반율 0 유지 확인 → 정책 JSON 커밋.
