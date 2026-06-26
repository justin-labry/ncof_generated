"""NCOF gNB2 전력 결정 문제의 Gymnasium 환경.

prototype의 룰 베이스 엔진(decide_wlan_gnb2_rule.py)이 푸는 것과 동일한
문제를 RL로 정식화한다:

    관측: WLAN aggregate DL throughput (현재/직전, 정규화) + 현재 gNB2 상태
    행동: 0 = DEEP_SLEEP, 1 = ACTIVE
    보상: 에너지 비용(3GPP TR 38.864 상대전력) + QoS 보호(수면 중 WLAN 과부하)
          + 상태 플랩 방지용 전환 비용

에너지 모델 (3GPP TR 38.864 V18.1.0, BS Category 1 Set 1):

    상대전력 P:  ACTIVE = 280,  DEEP_SLEEP = 1   (Table 5.1-3)
    전이에너지 E(deep sleep) = 1000 rel·ms = 1 rel·s  (Table 5.1-5)
    전이시간   T(deep sleep) = 50 ms                  (Table 5.1-4, Stage 2)

보상 항(스텝당, P_ACTIVE=280 으로 정규화하여 [0,1] 스케일):

    energy   = w_e * P(state) / 280          # ACTIVE→1.0, DEEP_SLEEP→0.0036
    qos      = w_q * max(0, wlan+gnb2_load-capacity) / 100   # 수면 중 과부하
    trans    = w_s (상태변경) + w_e * E/280 (active→deep 진입 시 1회)
    r = -(energy + qos + trans)

에너지(P)와 QoS 트레이드오프의 교차점이 WLAN 임계 부근에 놓이도록 설계 —
룰을 하드코딩하지 않고 RL이 38.864 전력모델 기반으로 정책을 학습한다.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .traffic import TrafficGenerator

DEEP_SLEEP, ACTIVE = 0, 1
ACTION_NAMES = ["DEEP_SLEEP", "ACTIVE"]

# prototype 쪽 추론기와 공유되는 관측 계약 (모델 JSON에 그대로 기록됨)
OBS_FEATURES = ["wlan_dl_norm", "prev_wlan_dl_norm", "gnb2_active"]
DEFAULT_NORM_MBPS = 1000.0

# 3GPP TR 38.864 V18.1.0 — BS Category 1, Set 1 (상대전력, deep sleep=1 기준)
P_ACTIVE = 280.0  # Table 5.1-3, Active DL
P_DEEP_SLEEP = 1.0  # Table 5.1-3, Deep sleep
E_TRANSITION_REL_S = 1.0  # Table 5.1-5, deep sleep 전이에너지 1000 rel·ms = 1 rel·s


class NcofGnb2Env(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = dict(config or {})
        self.norm_mbps = float(cfg.get("norm_mbps", DEFAULT_NORM_MBPS))
        self.wlan_capacity_mbps = float(cfg.get("wlan_capacity_mbps", 800.0))
        self.gnb2_load_mbps = float(cfg.get("gnb2_load_mbps", 300.0))
        self.gnb2_load_std = float(cfg.get("gnb2_load_std", 30.0))
        # 38.864 상대전력 (정규화 기준값)
        self.p_active = float(cfg.get("p_active", P_ACTIVE))
        self.p_deep_sleep = float(cfg.get("p_deep_sleep", P_DEEP_SLEEP))
        self.e_transition_rel_s = float(cfg.get("e_transition_rel_s", E_TRANSITION_REL_S))
        # 보상 가중치 (w_e: 에너지, w_q: QoS, w_s: 전이)
        self.energy_weight = float(cfg.get("energy_weight", 1.0))
        self.qos_weight = float(cfg.get("qos_weight", 5.0))
        self.switch_cost = float(cfg.get("switch_cost", 0.05))
        self.episode_len = int(cfg.get("episode_len", 288))
        self.traffic_mode = str(cfg.get("traffic_mode", "markov"))

        self.observation_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.0], dtype=np.float32),
            high=np.array([np.inf, np.inf, 1.0], dtype=np.float32),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(2)

        self._traffic: TrafficGenerator | None = None
        self._state = ACTIVE
        self._wlan = 0.0
        self._prev_wlan = 0.0
        self._t = 0

    def reset(self, *, seed: int | None = None, options=None):
        super().reset(seed=seed)
        self._traffic = TrafficGenerator(
            self.traffic_mode, self.np_random, episode_len=self.episode_len
        )
        self._state = ACTIVE
        self._wlan = self._traffic.sample()
        self._prev_wlan = self._wlan
        self._t = 0
        return self._obs(), {}

    def step(self, action):
        action = int(action)
        reward = 0.0
        info: dict[str, Any] = {
            "wlan_mbps": self._wlan,
            "action": ACTION_NAMES[action],
            "qos_violation": False,
        }

        # --- 에너지 비용: 38.864 상대전력을 P_ACTIVE로 정규화 (ACTIVE 1.0 / DEEP_SLEEP 0.0036) ---
        p_state = self.p_active if action == ACTIVE else self.p_deep_sleep
        reward -= self.energy_weight * (p_state / self.p_active)

        # --- QoS: 수면 중 gNB2 트래픽이 WLAN으로 오프로드, 용량 초과 시 위반 ---
        if action == DEEP_SLEEP:
            offload = self.gnb2_load_mbps + float(
                self.np_random.normal(0.0, self.gnb2_load_std)
            )
            total = self._wlan + max(0.0, offload)
            excess = total - self.wlan_capacity_mbps
            if excess > 0.0:
                reward -= self.qos_weight * excess / 100.0
                info["qos_violation"] = True

        # --- 전이: 상태 변경 시 switch cost + active→deep 진입 시 전이에너지 E (1회) ---
        if action != self._state:
            reward -= self.switch_cost
            if action == DEEP_SLEEP:  # active -> deep_sleep 진입 (E는 ramp down+up 포함)
                reward -= self.energy_weight * (self.e_transition_rel_s / self.p_active)

        self._state = action
        self._prev_wlan = self._wlan
        self._wlan = self._traffic.sample()
        self._t += 1

        truncated = self._t >= self.episode_len
        return self._obs(), float(reward), False, truncated, info

    def _obs(self) -> np.ndarray:
        return np.array(
            [
                self._wlan / self.norm_mbps,
                self._prev_wlan / self.norm_mbps,
                1.0 if self._state == ACTIVE else 0.0,
            ],
            dtype=np.float32,
        )
