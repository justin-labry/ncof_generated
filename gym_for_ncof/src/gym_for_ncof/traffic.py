"""WLAN(Non-3GPP) 트래픽 시계열 생성기.

NCOF 시나리오의 입력 신호인 12p_c(USER_DATA_USAGE_MEASURES)의
aggregate DL throughput을 흉내 낸다. 세 가지 모드:

- "markov": 저부하/고부하 2-regime 마르코프 전환 (기본, 학습용)
- "toggle": nsmf-server 목업과 동일한 블록 단위 고저 토글
- "sine":   하루 주기 사인 곡선 + 노이즈 (일반화 평가용)
"""

from __future__ import annotations

import math


class TrafficGenerator:
    def __init__(self, mode: str, rng, *, episode_len: int = 288):
        self.mode = mode
        self.rng = rng  # numpy Generator (env의 np_random 공유)
        self.episode_len = episode_len
        self._t = 0
        # markov regime: 0=low, 1=high
        self._regime = int(rng.random() < 0.5)
        # toggle: nsmf 목업처럼 일정 블록마다 고저 반전
        self._toggle_block = 6

    def sample(self) -> float:
        if self.mode == "markov":
            value = self._sample_markov()
        elif self.mode == "toggle":
            value = self._sample_toggle()
        elif self.mode == "sine":
            value = self._sample_sine()
        else:
            raise ValueError(f"unknown traffic mode: {self.mode}")
        self._t += 1
        return max(0.0, float(value))

    def _sample_markov(self) -> float:
        # regime 전환 확률 5% → 평균 20 스텝 체류
        if self.rng.random() < 0.05:
            self._regime = 1 - self._regime
        if self._regime == 1:
            return self.rng.normal(550.0, 40.0)
        return self.rng.normal(60.0, 25.0)

    def _sample_toggle(self) -> float:
        high = (self._t // self._toggle_block) % 2 == 0
        if high:
            return self.rng.uniform(500.0, 600.0)
        return self.rng.uniform(1.0, 100.0)

    def _sample_sine(self) -> float:
        phase = 2.0 * math.pi * self._t / self.episode_len
        return 400.0 + 300.0 * math.sin(phase) + self.rng.normal(0.0, 30.0)
