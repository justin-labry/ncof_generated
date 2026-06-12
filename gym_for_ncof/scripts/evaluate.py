#!/usr/bin/env python3
"""학습된 RL 정책 vs 룰 베이스(500 Mbps 임계) 비교 평가.

ray 불필요 — 환경 + JSON 정책만으로 평가한다.

실행 (gym_for_ncof/ 에서):
    uv run python scripts/evaluate.py
    uv run python scripts/evaluate.py --episodes 20 --policy models/gnb2_policy.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gym_for_ncof.env import ACTION_NAMES, ACTIVE, DEEP_SLEEP, NcofGnb2Env  # noqa: E402
from gym_for_ncof.policy_export import load_policy, policy_action  # noqa: E402

RULE_TH_MBPS = 500.0  # prototype 룰 베이스와 동일 임계


def rule_action(wlan_mbps: float) -> int:
    return ACTIVE if wlan_mbps >= RULE_TH_MBPS else DEEP_SLEEP


def rollout(env: NcofGnb2Env, policy, episodes: int, seed0: int):
    """policy: obs(list[float]) -> action(int). 통계 dict 반환."""
    total_reward = 0.0
    steps = active_steps = violations = agree = 0
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed0 + ep)
        done = False
        while not done:
            wlan_mbps = float(obs[0]) * env.norm_mbps
            action = policy(obs.tolist())
            if action == rule_action(wlan_mbps):
                agree += 1
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1
            active_steps += int(info["action"] == "ACTIVE")
            violations += int(info["qos_violation"])
    return {
        "mean_episode_return": total_reward / episodes,
        "active_ratio": active_steps / steps,
        "qos_violation_ratio": violations / steps,
        "rule_agreement": agree / steps,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument(
        "--policy", type=Path, default=REPO / "models/gnb2_policy.json"
    )
    args = parser.parse_args()

    policy_json = load_policy(args.policy)

    def rl_policy(obs: list[float]) -> int:
        return ACTION_NAMES.index(policy_action(policy_json, obs))

    def baseline_policy(obs: list[float]) -> int:
        return rule_action(obs[0] * 1000.0)

    for mode in ("markov", "toggle", "sine"):
        env = NcofGnb2Env({"traffic_mode": mode})
        rl = rollout(env, rl_policy, args.episodes, seed0=1000)
        rb = rollout(env, baseline_policy, args.episodes, seed0=1000)
        print(f"\n=== traffic_mode={mode} ({args.episodes} episodes) ===")
        print(f"{'':22s}{'RL':>12s}{'rule(500)':>12s}")
        for key in (
            "mean_episode_return",
            "active_ratio",
            "qos_violation_ratio",
            "rule_agreement",
        ):
            print(f"{key:22s}{rl[key]:>12.3f}{rb[key]:>12.3f}")


if __name__ == "__main__":
    main()
