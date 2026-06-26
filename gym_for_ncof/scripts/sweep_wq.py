#!/usr/bin/env python3
"""QoS 가중치(w_q) 스윕.

각 w_q 값으로 PPO 정책을 학습시킨 뒤 markov/toggle/sine 트래픽에서
behavior(active 비율 = 에너지 proxy, QoS 위반율, 스텝당 상대전력)를 측정한다.
목표: QoS 위반율 ≈ 0 을 유지하면서 active 비율(에너지)이 가장 낮은 w_q.

실행 (gym_for_ncof/ 에서):
    uv run python scripts/sweep_wq.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from gym_for_ncof.env import (  # noqa: E402
    NcofGnb2Env, P_ACTIVE, P_DEEP_SLEEP, DEFAULT_NORM_MBPS,
)

WQ_VALUES = [1.0, 2.0, 3.0, 5.0, 8.0]
ITERS = 35
EP = 15
MODES = ["markov", "toggle", "sine"]


def build_algo(wq: float):
    from ray.rllib.algorithms.ppo import PPOConfig
    cfg = (
        PPOConfig()
        .environment(NcofGnb2Env, env_config={
            "traffic_mode": "markov", "norm_mbps": DEFAULT_NORM_MBPS, "qos_weight": wq})
        .framework("torch")
        .env_runners(num_env_runners=4)
        .training(lr=3e-4, gamma=0.99, train_batch_size=8000)
    )
    try:
        from ray.rllib.core.rl_module.default_model_config import DefaultModelConfig
        cfg = cfg.rl_module(model_config=DefaultModelConfig(
            fcnet_hiddens=[64, 64], fcnet_activation="relu"))
    except ImportError:
        cfg = cfg.training(model={"fcnet_hiddens": [64, 64], "fcnet_activation": "relu"})
    build = getattr(cfg, "build_algo", None) or cfg.build
    return build()


def act(module, obs: np.ndarray) -> int:
    with torch.no_grad():
        out = module.forward_inference({"obs": torch.from_numpy(obs.reshape(1, -1))})
    return int(np.asarray(out["action_dist_inputs"]).argmax())


def evaluate(module) -> dict:
    res = {}
    for mode in MODES:
        env = NcofGnb2Env({"traffic_mode": mode})
        steps = active = viol = 0
        energy = 0.0
        for ep in range(EP):
            obs, _ = env.reset(seed=1000 + ep)
            done = False
            while not done:
                a = act(module, obs)
                obs, _, term, trunc, info = env.step(a)
                done = term or trunc
                steps += 1
                active += int(info["action"] == "ACTIVE")
                viol += int(info["qos_violation"])
                energy += P_ACTIVE if info["action"] == "ACTIVE" else P_DEEP_SLEEP
        res[mode] = {"active": active / steps, "viol": viol / steps,
                     "E": energy / steps}
    return res


def main() -> None:
    rows = []
    for wq in WQ_VALUES:
        print(f"\n=== training w_q={wq} ({ITERS} iters) ===", flush=True)
        algo = build_algo(wq)
        for _ in range(ITERS):
            algo.train()
        r = evaluate(algo.get_module("default_policy"))
        algo.stop()
        rows.append((wq, r))
        for m in MODES:
            print(f"  w_q={wq} {m:6s}: active={r[m]['active']:.3f} "
                  f"viol={r[m]['viol']:.3f} E/step={r[m]['E']:.1f}", flush=True)

    print("\n===== SWEEP SUMMARY (active = energy proxy; 낮을수록 절감) =====", flush=True)
    hdr = f"{'w_q':>5} | {'markov a/v':>14} | {'toggle a/v':>14} | {'sine a/v':>14} | {'avgE/step':>9}"
    print(hdr, flush=True)
    print("-" * len(hdr), flush=True)
    for wq, r in rows:
        avgE = sum(r[m]["E"] for m in MODES) / 3
        print(f"{wq:>5} | {r['markov']['active']:.2f}/{r['markov']['viol']:.3f}  "
              f"| {r['toggle']['active']:.2f}/{r['toggle']['viol']:.3f}  "
              f"| {r['sine']['active']:.2f}/{r['sine']['viol']:.3f}  "
              f"| {avgE:>9.1f}", flush=True)


if __name__ == "__main__":
    main()
