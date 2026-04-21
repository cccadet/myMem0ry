"""Tests for dataset modules — filters, deduplication, splitting, stats."""

from __future__ import annotations

from mem0ry.dataset.dedupe import deduplicate_examples
from mem0ry.dataset.filter import apply_quality_filters
from mem0ry.dataset.splitter import train_val_split
from mem0ry.dataset.stats import DatasetStats, compute_stats


def _make_example(messages: list[dict[str, str]]) -> dict:
    return {"messages": messages, "metadata": {}}


def test_quality_filters_removes_short() -> None:
    examples = [
        _make_example([{"role": "user", "content": "ok"}]),
    ]
    result = apply_quality_filters(examples, min_turns=2)
    assert len(result) == 0


def test_quality_filters_keeps_valid() -> None:
    examples = [
        _make_example([
            {"role": "user", "content": "Tell me about Python programming"},
            {"role": "assistant", "content": "Python is a versatile programming language"},
        ]),
    ]
    result = apply_quality_filters(examples, min_turns=2)
    assert len(result) == 1


def test_deduplicate_removes_duplicates() -> None:
    ex = _make_example([{"role": "user", "content": "hello"}])
    result = deduplicate_examples([ex, ex])
    assert len(result) == 1
    assert "content_hash" in result[0]["metadata"]


def test_deduplicate_keeps_unique() -> None:
    ex1 = _make_example([{"role": "user", "content": "hello"}])
    ex2 = _make_example([{"role": "user", "content": "world"}])
    result = deduplicate_examples([ex1, ex2])
    assert len(result) == 2


def test_train_val_split() -> None:
    examples = [{"i": i} for i in range(100)]
    train, val = train_val_split(examples, val_ratio=0.1)
    assert len(val) == 10
    assert len(train) == 90


def test_train_val_split_empty() -> None:
    train, val = train_val_split([])
    assert train == []
    assert val == []


def test_compute_stats() -> None:
    examples = [
        _make_example([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]),
    ]
    stats = compute_stats(examples)
    assert isinstance(stats, DatasetStats)
    assert stats.total_examples == 1
    assert stats.avg_messages == 2.0
    d = stats.to_dict()
    assert d["total_examples"] == 1


def test_compute_stats_empty() -> None:
    stats = compute_stats([])
    assert stats.total_examples == 0
