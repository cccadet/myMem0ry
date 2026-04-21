"""Tests for config — MemoryConfig defaults."""

from __future__ import annotations

from mem0ry.config import MemoryConfig


def test_defaults() -> None:
    config = MemoryConfig()
    assert config.expand_top_k == 10
    assert config.search_top_k == 3
    assert config.search_backend == "ripgrep"
    assert config.spacy_model == "pt_core_news_lg"
    assert config.system_prompt is None


def test_custom_values() -> None:
    config = MemoryConfig(expand_top_k=5, search_backend="bm25")
    assert config.expand_top_k == 5
    assert config.search_backend == "bm25"
