# gym_for_ncof

NCOF의 gNB2 전력 결정(DEEP_SLEEP/ACTIVE)을 강화학습으로 대체하기 위한
Gymnasium 환경 + RLlib(PPO) 학습 파이프라인.

prototype의 룰 베이스 엔진(`Gnb2RuleEngine`, 500 Mbps 단일 임계)과 동일한
입출력 인터페이스를 유지하므로, 학습된 정책을 `Gnb2RLEngine`으로 갈아끼우면
NCOF의 나머지 로직(emit-on-change, dwell guard, 15f/14_e 생성·발송)은 그대로
동작한다. (시나리오 문서 §12 "엔진 한 줄 교체" 약속의 구현)

## 구조

```
gym_for_ncof/
├── src/gym_for_ncof/
│   ├── env.py            # NcofGnb2Env (Gymnasium)
│   ├── traffic.py        # WLAN 트래픽 생성기 (markov/toggle/sine)
│   └── policy_export.py  # torch → JSON 가중치 export + 순수파이썬 추론
├── scripts/
│   ├── train.py          # RLlib PPO 학습 → models/gnb2_policy.json
│   └── evaluate.py       # RL vs 룰(500Mbps) 비교 평가 (ray 불필요)
└── models/
    └── gnb2_policy.json  # 학습 산출물 — prototype이 읽는 유일한 파일
```

## MDP 정의

| 항목 | 내용 |
|---|---|
| 관측 | `[wlan_dl/1000, prev_wlan_dl/1000, gnb2_active(0/1)]` |
| 행동 | `0=DEEP_SLEEP`, `1=ACTIVE` |
| 보상 | ACTIVE: `-energy_cost(0.5)` / DEEP_SLEEP 중 WLAN 과부하: `-5.0 × 초과Mbps/100` / 상태 전환: `-0.05` |
| 에피소드 | 288 스텝 (5분 단위 하루) |

보상 경제학이 만드는 최적 임계 ≈ `capacity(800) − gnb2_load(300) + 100×0.5/5.0 = 510 Mbps`
→ **룰을 하드코딩하지 않아도 RL이 500 Mbps 부근의 정책을 보상만으로 학습**한다.

## 사용법

```bash
cd gym_for_ncof
uv sync                              # gymnasium + ray[rllib] + torch(CPU)

uv run python scripts/train.py       # PPO 학습 (기본 40 iter) → models/gnb2_policy.json
uv run python scripts/evaluate.py    # RL vs 룰 비교 (traffic 3종 모드)
```

- GPU 학습이 필요하면 `pyproject.toml`의 `pytorch-cpu` index 블록을 제거.
- 학습 산출물 `models/gnb2_policy.json`은 의존성 없는 MLP 가중치
  (`ncof-gnb2-mlp-v1` 포맷)이며, export 시 원본 RLlib 정책과 행동 일치를
  자동 검증한다(불일치 시 export 실패).

## prototype(NCOF 서버)에서 RL 엔진 사용

nncof-server는 ray/torch 없이 JSON만 읽어 순수 파이썬으로 추론한다
(`nncof/core/gnb2_rl_engine.py`).

```bash
cd prototype/nncof-server
NCOF_DECISION_ENGINE=rl sh run.sh                 # 기본 경로의 정책 사용
# 또는
NCOF_DECISION_ENGINE=rl \
NCOF_RL_POLICY_PATH=/path/to/gnb2_policy.json sh run.sh
```

- 미설정/`rule`(기본): 기존 룰 베이스 엔진 사용 — 데모 안전 기본값.
- 정책 파일 로드 실패 시 경고 로그 후 룰 베이스로 자동 폴백.
