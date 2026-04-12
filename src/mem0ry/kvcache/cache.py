"""KV Cache serialization and deserialization."""

from __future__ import annotations

from pathlib import Path

import torch


def save_kv(past_key_values, path: Path) -> None:
    data = []
    for layer in past_key_values:
        k, v = layer[0], layer[1]
        data.append(
            {
                "k_shape": list(k.shape),
                "v_shape": list(v.shape),
                "k": k.cpu().to(torch.float32).numpy().tobytes(),
                "v": v.cpu().to(torch.float32).numpy().tobytes(),
            }
        )
    torch.save(data, path)


def load_kv(path: Path, device: str, dtype: torch.dtype) -> tuple:
    data = torch.load(path, map_location="cpu", weights_only=False)
    past = []
    for layer in data:
        k = (
            torch.frombuffer(layer["k"], dtype=torch.float32)
            .reshape(layer["k_shape"])
            .to(dtype)
            .to(device)
        )
        v = (
            torch.frombuffer(layer["v"], dtype=torch.float32)
            .reshape(layer["v_shape"])
            .to(dtype)
            .to(device)
        )
        past.append((k, v))
    return tuple(past)
