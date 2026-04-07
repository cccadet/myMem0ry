"""Statistics for ChatML datasets."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence


@dataclass
class DatasetStats:
    total_examples: int
    avg_messages: float
    max_messages: int
    min_messages: int
    avg_chars: float
    total_chars: int

    def to_dict(self) -> dict[str, int | float]:
        return {
            "total_examples": self.total_examples,
            "avg_messages": self.avg_messages,
            "max_messages": self.max_messages,
            "min_messages": self.min_messages,
            "avg_chars": self.avg_chars,
            "total_chars": self.total_chars,
        }


def compute_stats(examples: Sequence[dict]) -> DatasetStats:
    total_examples = len(examples)
    if not examples:
        return DatasetStats(0, 0.0, 0, 0, 0.0, 0)

    message_counts = [len(ex.get("messages", [])) for ex in examples]
    char_counts = [
        sum(len(msg.get("content", "")) for msg in ex.get("messages", []))
        for ex in examples
    ]

    return DatasetStats(
        total_examples=total_examples,
        avg_messages=float(mean(message_counts)),
        max_messages=max(message_counts, default=0),
        min_messages=min(message_counts, default=0),
        avg_chars=float(mean(char_counts)) if char_counts else 0.0,
        total_chars=sum(char_counts),
    )
