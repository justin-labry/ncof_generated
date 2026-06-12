"""학습된 RLlib 정책을 의존성 없는 JSON 가중치로 내보내고, 그 JSON으로
추론하는 순수 파이썬 forward pass를 제공한다.

prototype(nncof-server)은 ray/torch 없이 이 JSON만 읽어 추론한다.
여기 있는 ``mlp_forward``가 그 추론의 레퍼런스 구현이며, export 시점에
원본 RLlib 정책과 행동이 100% 일치하는지 검증한다.

JSON 계약 (format: ncof-gnb2-mlp-v1):
    {
      "format": "ncof-gnb2-mlp-v1",
      "activation": "relu",                  # 마지막 레이어 제외 모든 레이어 뒤
      "actions": ["DEEP_SLEEP", "ACTIVE"],   # argmax 인덱스 → 상태 문자열
      "obs": {"features": [...], "norm_mbps": 1000.0},
      "layers": [{"name": ..., "w": [[...]], "b": [...]}, ...]
    }
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

FORMAT = "ncof-gnb2-mlp-v1"

# 가치(critic) 경로의 Linear는 정책 추론에 불필요 → 이름으로 제외
_EXCLUDE_NAME_KEYWORDS = ("vf", "value", "critic")


def mlp_forward(layers: list[dict], activation: str, x: list[float]) -> list[float]:
    """순수 파이썬 MLP forward (prototype 추론기와 동일 로직)."""
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


def policy_action(policy: dict, obs: list[float]) -> str:
    logits = mlp_forward(policy["layers"], policy["activation"], obs)
    idx = max(range(len(logits)), key=lambda i: logits[i])
    return policy["actions"][idx]


def load_policy(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        policy = json.load(f)
    if policy.get("format") != FORMAT:
        raise ValueError(f"unsupported policy format: {policy.get('format')}")
    return policy


def _collect_actor_linears(torch_module) -> list[tuple[str, Any]]:
    import torch.nn as nn

    linears = []
    for name, mod in torch_module.named_modules():
        if isinstance(mod, nn.Linear):
            lname = name.lower()
            if any(k in lname for k in _EXCLUDE_NAME_KEYWORDS):
                continue
            linears.append((name, mod))
    if not linears:
        raise RuntimeError("no actor Linear layers found in module")
    return linears


def export_rl_module_to_json(
    rl_module,
    path: str | Path,
    *,
    obs_features: list[str],
    norm_mbps: float,
    actions: list[str],
    activation: str = "relu",
    validate_samples: int = 512,
) -> dict:
    """RLlib(torch) 모듈에서 actor 경로 Linear들을 추출해 JSON으로 저장.

    저장 전에 원본 모듈의 forward_inference와 순수 파이썬 forward의
    argmax 행동이 모든 검증 샘플에서 일치하는지 확인한다. 불일치 시
    레이어 구조가 가정과 다른 것이므로 즉시 실패시킨다.
    """
    import numpy as np
    import torch

    named = _collect_actor_linears(rl_module)
    layers = [
        {
            "name": name,
            "w": mod.weight.detach().cpu().tolist(),
            "b": mod.bias.detach().cpu().tolist(),
        }
        for name, mod in named
    ]

    obs_dim = len(layers[0]["w"][0])
    out_dim = len(layers[-1]["w"])
    if obs_dim != len(obs_features):
        raise RuntimeError(
            f"first layer expects obs dim {obs_dim}, "
            f"but obs_features has {len(obs_features)}"
        )
    if out_dim != len(actions):
        raise RuntimeError(
            f"last layer outputs {out_dim} logits for {len(actions)} actions "
            f"(layers: {[l['name'] for l in layers]})"
        )

    policy = {
        "format": FORMAT,
        "activation": activation,
        "actions": list(actions),
        "obs": {"features": list(obs_features), "norm_mbps": norm_mbps},
        "layers": layers,
    }

    # --- 검증: 원본 정책 vs JSON 추론의 행동 일치 ---
    rng = np.random.default_rng(0)
    obs_batch = rng.uniform(0.0, 1.0, size=(validate_samples, obs_dim)).astype(
        np.float32
    )
    obs_batch[:, -1] = rng.integers(0, 2, size=validate_samples)  # gnb2_active는 0/1

    with torch.no_grad():
        out = rl_module.forward_inference({"obs": torch.from_numpy(obs_batch)})
    logits = out["action_dist_inputs"].cpu().numpy()
    ref_actions = logits.argmax(axis=-1)

    mismatches = 0
    for i in range(validate_samples):
        json_logits = mlp_forward(layers, activation, obs_batch[i].tolist())
        if int(np.argmax(json_logits)) != int(ref_actions[i]):
            mismatches += 1
    if mismatches:
        raise RuntimeError(
            f"export validation failed: {mismatches}/{validate_samples} action "
            f"mismatches (layers: {[l['name'] for l in layers]})"
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(policy, f)
    return policy
