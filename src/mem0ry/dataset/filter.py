"""Quality filters to keep only useful ChatML sequences."""

from __future__ import annotations

from typing import Sequence


def apply_quality_filters(
    examples: Sequence[dict], *, min_turns: int = 2, min_length: int = 8
) -> list[dict]:
    """Drop examples that are too short, empty, or system-only."""
    return [
        ex for ex in examples if _has_quality_content(ex, min_turns, min_length)
    ]


def _has_quality_content(
    example: dict, min_turns: int, min_length: int
) -> bool:
    """Check whether a single example meets quality thresholds."""
    messages = example.get("messages", [])
    roles = [m.get("role") for m in messages if m.get("content")]
    if len(roles) < min_turns:
        return False
    trimmed = [
        c.strip() for c in (m.get("content", "") for m in messages)
        if c and c.strip()
    ]
    if not trimmed:
        return False
    return max(len(p) for p in trimmed) >= min_length
