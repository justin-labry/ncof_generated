"""강화학습 정책 기반 gNB2 결정 엔진.

gym_for_ncof에서 RLlib(PPO)으로 학습한 정책을 JSON 가중치
(ncof-gnb2-mlp-v1 포맷)로 받아, ray/torch 의존성 없이 순수 파이썬
forward pass로 추론한다. 판정(_decide)만 교체하고 emit-on-change,
minimum-dwell guard, 15f/14_e 생성은 Gnb2RuleEngine 공통 로직을 그대로
사용한다 — 시나리오 문서 §12의 "엔진 한 줄 교체" 인터페이스 약속 구현.

활성화 (nncof-server 실행 환경):
    NCOF_DECISION_ENGINE=rl
    NCOF_RL_POLICY_PATH=/path/to/gnb2_policy.json   # 생략 시 리포 기본 경로
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path

from .gnb2_rule_engine import Gnb2RuleEngine

logger = logging.getLogger(__name__)

POLICY_FORMAT = "ncof-gnb2-mlp-v1"

# core/ → nncof → src → nncof-server → prototype → (repo root)
_DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[5] / "gym_for_ncof/models/gnb2_policy.json"
)


def _mlp_forward(layers: list[dict], activation: str, x: list[float]) -> list[float]:
    for i, layer in enumerate(layers):
        w, b = layer["w"], layer["b"]
        x = [
            sum(wij * xj for wij, xj in zip(row, x)) + bi
            for row, bi in zip(w, b)
        ]
        if i < len(layers) - 1:
            if activation == "relu":
                x = [v if v > 0.0 else 0.0 for v in x]
            elif activation == "tanh":
                x = [math.tanh(v) for v in x]
            else:
                raise ValueError(f"unsupported activation: {activation}")
    return x


class Gnb2RLEngine(Gnb2RuleEngine):
    def __init__(self, policy_path: str | Path, min_dwell_sec: int = 0):
        super().__init__(min_dwell_sec=min_dwell_sec)
        with open(policy_path, encoding="utf-8") as f:
            self._policy = json.load(f)
        if self._policy.get("format") != POLICY_FORMAT:
            raise ValueError(
                f"unsupported policy format: {self._policy.get('format')}"
            )
        self._features: list[str] = self._policy["obs"]["features"]
        self._norm_mbps: float = float(self._policy["obs"]["norm_mbps"])
        self._actions: list[str] = self._policy["actions"]
        self._prev_metric: float | None = None
        logger.info(
            "Gnb2RLEngine loaded: %s (obs=%s, actions=%s)",
            policy_path,
            self._features,
            self._actions,
        )

    def _build_obs(self, metric: float) -> list[float]:
        prev = self._prev_metric if self._prev_metric is not None else metric
        active = 1.0 if self.last_emitted_state == "ACTIVE" else 0.0
        values = {
            "wlan_dl_norm": metric / self._norm_mbps,
            "prev_wlan_dl_norm": prev / self._norm_mbps,
            "gnb2_active": active,
        }
        try:
            return [values[name] for name in self._features]
        except KeyError as e:
            raise ValueError(f"policy requires unknown obs feature: {e}") from e

    def _decide(self, metric: float) -> str:
        obs = self._build_obs(metric)
        self._prev_metric = metric
        logits = _mlp_forward(
            self._policy["layers"], self._policy["activation"], obs
        )
        idx = max(range(len(logits)), key=lambda i: logits[i])
        state = self._actions[idx]
        logger.info(
            "[RL] metric=%.1f Mbps obs=%s -> %s", metric, [round(v, 3) for v in obs], state
        )
        return state


def create_decision_engine(min_dwell_sec: int = 0) -> Gnb2RuleEngine:
    """
    환경변수 NCOF_DECISION_ENGINE(rule|rl)에 따라 결정 엔진을 생성한다.
    RL 정책 로드 실패 시 룰 베이스로 폴백한다 (데모 안전장치).
    """
    engine_kind = os.getenv("NCOF_DECISION_ENGINE", "rule").strip().lower()
    if engine_kind == "rl":
        policy_path = os.getenv("NCOF_RL_POLICY_PATH", str(_DEFAULT_POLICY_PATH))
        try:
            return Gnb2RLEngine(policy_path, min_dwell_sec=min_dwell_sec)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "RL 정책 로드 실패(%s: %s) — 룰 베이스 엔진으로 폴백",
                policy_path,
                e,
            )
    return Gnb2RuleEngine(min_dwell_sec=min_dwell_sec)
