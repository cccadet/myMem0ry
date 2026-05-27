"""Tests for conversations.benchmark — run_benchmark and format_table."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

from mem0ry.conversations.benchmark import run_benchmark, format_table


def test_format_table_basic() -> None:
    results = [
        {"backend": "ripgrep", "time_ms": 10.5, "n_files": 3, "paths": [Path("a.md")]},
        {"backend": "bm25", "time_ms": 5.2, "n_files": 2, "paths": [Path("b.md")]},
        {"backend": "fts5", "time_ms": -1, "n_files": 0, "paths": []},
    ]
    table = format_table(results)
    assert "ripgrep" in table
    assert "10.5" in table
    assert "bm25" in table
    assert "fts5" in table
    assert "a.md" in table
    assert "-" in table


def test_format_table_empty() -> None:
    table = format_table([])
    assert "Backend" in table


def test_run_benchmark_calls_backends(tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("python content", encoding="utf-8")

    mock_rg = MagicMock(return_value=[tmp_path / "test.md"])
    mock_bm25 = MagicMock(return_value=[tmp_path / "test.md"])
    mock_fts = MagicMock(return_value=[])

    with (
        patch("mem0ry.conversations.benchmark.search", mock_rg),
        patch("mem0ry.conversations.benchmark.search_bm25", mock_bm25),
        patch("mem0ry.conversations.benchmark.search_fts", mock_fts),
    ):
        results = run_benchmark("python", tmp_path, top_k=3)

    assert len(results) == 3
    assert results[0]["backend"] == "ripgrep"
    assert results[0]["time_ms"] >= 0
    assert results[0]["n_files"] == 1
    assert results[1]["backend"] == "bm25"
    assert results[2]["backend"] == "fts5"


def test_run_benchmark_handles_error(tmp_path: Path) -> None:
    mock_rg = MagicMock(side_effect=RuntimeError("boom"))

    with (
        patch("mem0ry.conversations.benchmark.search", mock_rg),
        patch("mem0ry.conversations.benchmark.search_bm25", MagicMock(return_value=[])),
        patch("mem0ry.conversations.benchmark.search_fts", MagicMock(return_value=[])),
    ):
        results = run_benchmark("test", tmp_path)

    assert results[0]["backend"] == "ripgrep"
    assert results[0]["time_ms"] == -1
    assert results[0]["n_files"] == 0
