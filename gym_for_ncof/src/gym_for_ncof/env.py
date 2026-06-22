"""NCOF gNB2 전력 결정 문제의 Gymnasium 환경.

prototype의 룰 베이스 엔진(decide_wlan_gnb2_rule.py)이 푸는 것과 동일한
문제를 RL로 정식화한다:

    관측: WLAN aggregate DL throughput (현재/직전, 정규화) + 현재 gNB2 상태
    행동: 0 = DEEP_SLEEP, 1 = ACTIVE
    보상: 에너지 절감(ACTIVE 비용) vs QoS 보호(수면 중 WLAN 과부하 페널티)
          + 상태 플랩 방지용 전환 비용

보상 경제학(기본값 기준)이 만드는 최적 임계점:

    수면 비용  = qos_penalty * max(0, wlan + gnb2_load - capacity) / 100
    ACTIVE 비용 = energy_cost
    교차점: wlan* = capacity - gnb2_load + 100*energy_cost/qos_penalty
          = 800 - 300 + 100*0.5/5.0 = 510 Mbps

즉 학습이 잘 되면 룰 베이스의 500 Mbps 임계와 거의 같은 정책이 보상만으로
유도된다 — 룰을 하드코딩하지 않고 RL이 스스로 찾는다는 데모 포인트.
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


class NcofGnb2Env(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = dict(config or {})
        self.norm_mbps = float(cfg.get("norm_mbps", DEFAULT_NORM_MBPS))
        self.wlan_capacity_mbps = float(cfg.get("wlan_capacity_mbps", 800.0))
        self.gnb2_load_mbps = float(cfg.get("gnb2_load_mbps", 300.0))
        self.gnb2_load_std = float(cfg.get("gnb2_load_std", 30.0))
        self.energy_cost = float(cfg.get("energy_cost", 0.5))
        self.qos_penalty_per_100mbps = float(cfg.get("qos_penalty_per_100mbps", 5.0))
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

        if action == ACTIVE:
            reward -= self.energy_cost
        else:
            # 수면 중에는 gNB2 트래픽이 WLAN으로 오프로드된다고 가정
            offload = self.gnb2_load_mbps + float(
                self.np_random.normal(0.0, self.gnb2_load_std)
            )
            total = self._wlan + max(0.0, offload)
            excess = total - self.wlan_capacity_mbps
            if excess > 0.0:
                reward -= self.qos_penalty_per_100mbps * excess / 100.0
                info["qos_violation"] = True

        if action != self._state:
            reward -= self.switch_cost

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
