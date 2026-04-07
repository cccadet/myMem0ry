"""Train/validation split helpers."""

from __future__ import annotations

import random
from typing import Sequence, Tuple


def train_val_split(
    examples: Sequence[dict], *, val_ratio: float = 0.05, seed: int = 42
) -> Tuple[list[dict], list[dict]]:
    values = list(examples)
    if not values:
        return [], []
    random.Random(seed).shuffle(values)
    val_size = max(1, int(len(values) * val_ratio)) if len(values) > 1 else 0
    if val_size >= len(values):
        val_size = len(values) // 2
    val = values[:val_size]
    train = values[val_size:]
    return train, val
