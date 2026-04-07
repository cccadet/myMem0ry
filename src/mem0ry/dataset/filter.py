"""Quality filters to keep only useful ChatML sequences."""

from __future__ import annotations

from typing import Sequence


def apply_quality_filters(
    examples: Sequence[dict], *, min_turns: int = 2, min_length: int = 8
) -> list[dict]:
    """Drop examples that are too short, empty, or system-only."""
    result: list[dict] = []
    for example in examples:
        roles = [
            msg.get("role") for msg in example.get("messages", []) if msg.get("content")
        ]
        contents = [msg.get("content", "") for msg in example.get("messages", [])]
        if len(roles) < min_turns:
            continue
        trimmed = [
            content.strip() for content in contents if content and content.strip()
        ]
        if not trimmed:
            continue
        if max(len(piece) for piece in trimmed) < min_length:
            continue
        result.append(example)
    return result
