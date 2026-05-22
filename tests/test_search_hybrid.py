"""Tests for conversations.search_hybrid — RRF fusion search."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from mem0ry.conversations.search_hybrid import _rrf_fuse, search_hybrid


def test_rrf_fuse_single_list() -> None:
    result = _rrf_fuse(["a", "b", "c"])
    assert result[0][0] == "a"
    assert result[0][1] > result[1][1]


def test_rrf_fuse_two_lists_agreement() -> None:
    result = _rrf_fuse(["a", "b", "c"], ["a", "b", "d"])
    paths = [p for p, _ in result]
    assert paths[0] == "a"
    assert paths[1] == "b"


def test_rrf_fuse_disjoint_lists() -> None:
    result = _rrf_fuse(["x", "y"], ["a", "b"])
    paths = [p for p, _ in result]
    assert len(paths) == 4


def test_rrf_fuse_empty() -> None:
    result = _rrf_fuse([], [])
    assert result == []


def test_rrf_fuse_custom_k() -> None:
    result_k1 = _rrf_fuse(["a", "b"], ["b", "a"], k=1)
    result_k100 = _rrf_fuse(["a", "b"], ["b", "a"], k=100)
    assert len(result_k1) == 2
    assert len(result_k100) == 2


def test_search_hybrid_returns_paths(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    d = conv_dir / "2026-01-01"
    d.mkdir(parents=True)
    (d / "python.md").write_text("python programming language", encoding="utf-8")
    (d / "other.md").write_text("cooking recipes", encoding="utf-8")

    fake_encoder = MagicMock()
    fake_encoder.encode.return_value = np.ones(300, dtype=np.float32)

    fake_store = MagicMock()
    fake_store.query.return_value = [
        ("2026-01-01/python.md", 0.1),
        ("2026-01-01/other.md", 0.9),
    ]

    with patch(
        "mem0ry.conversations.search_hybrid.search_bm25",
        return_value=[d / "python.md"],
    ):
        results = search_hybrid(
            "python", conv_dir, fake_encoder, fake_store, top_k=3
        )

    assert len(results) >= 1
    assert all(isinstance(p, Path) for p in results)


def test_search_hybrid_empty_results(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()

    fake_encoder = MagicMock()
    fake_encoder.encode.return_value = np.zeros(8, dtype=np.float32)
    fake_store = MagicMock()
    fake_store.query.return_value = []

    with patch(
        "mem0ry.conversations.search_hybrid.search_bm25",
        return_value=[],
    ):
        results = search_hybrid("query", conv_dir, fake_encoder, fake_store)

    assert results == []
