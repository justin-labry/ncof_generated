#!/usr/bin/env python3
"""RLlib PPO로 NcofGnb2Env 정책을 학습하고 JSON 가중치로 내보낸다.

실행 (gym_for_ncof/ 에서):
    uv run python scripts/train.py                 # 기본 40 iteration
    uv run python scripts/train.py --iters 80
    uv run python scripts/train.py --out models/gnb2_policy.json

산출물:
    models/gnb2_policy.json   # prototype이 읽는 의존성-제로 정책 가중치
    runs/<timestamp>/         # RLlib 체크포인트 (재학습/디버깅용, best-effort)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gym_for_ncof.env import (  # noqa: E402
    ACTION_NAMES,
    DEFAULT_NORM_MBPS,
    OBS_FEATURES,
    NcofGnb2Env,
)
from gym_for_ncof.policy_export import export_rl_module_to_json  # noqa: E402

ENV_CONFIG = {"traffic_mode": "markov", "norm_mbps": DEFAULT_NORM_MBPS}


def build_algo():
    from ray.rllib.algorithms.ppo import PPOConfig

    config = (
        PPOConfig()
        .environment(NcofGnb2Env, env_config=ENV_CONFIG)
        .framework("torch")
        .env_runners(num_env_runners=4)
        .training(lr=3e-4, gamma=0.99, train_batch_size=8000)
    )

    # 작은 MLP로 고정 (export 계약: relu, 마지막 레이어 = 액션 logits)
    try:
        from ray.rllib.core.rl_module.default_model_config import DefaultModelConfig

        config = config.rl_module(
            model_config=DefaultModelConfig(
                fcnet_hiddens=[64, 64], fcnet_activation="relu"
            )
        )
    except ImportError:
        config = config.training(
            model={"fcnet_hiddens": [64, 64], "fcnet_activation": "relu"}
        )

    build = getattr(config, "build_algo", None) or config.build
    return build()


def episode_return(result: dict) -> float | None:
    for path in (
        ("env_runners", "episode_return_mean"),
        ("episode_reward_mean",),
        ("sampler_results", "episode_reward_mean"),
    ):
        node = result
        for key in path:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if isinstance(node, (int, float)):
            return float(node)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iters", type=int, default=40)
    parser.add_argument("--out", type=Path, default=REPO / "models/gnb2_policy.json")
    args = parser.parse_args()

    algo = build_algo()
    for i in range(1, args.iters + 1):
        result = algo.train()
        ret = episode_return(result)
        print(f"iter {i:3d}/{args.iters}  episode_return_mean={ret}")

    # 체크포인트 저장 (best-effort: JSON export가 본 산출물)
    try:
        run_dir = REPO / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        saved = algo.save(str(run_dir))
        print(f"checkpoint: {saved}")
    except Exception as e:  # noqa: BLE001
        print(f"checkpoint save skipped: {e}")

    module = algo.get_module("default_policy")
    export_rl_module_to_json(
        module,
        args.out,
        obs_features=OBS_FEATURES,
        norm_mbps=ENV_CONFIG["norm_mbps"],
        actions=ACTION_NAMES,
        activation="relu",
    )
    print(f"exported policy: {args.out}")

    algo.stop()


if __name__ == "__main__":
    main()
