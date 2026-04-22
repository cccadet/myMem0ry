"""Tests for cli.main — Typer CLI commands via CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mem0ry.cli.main import app

runner = CliRunner()


def test_split_no_source(tmp_path: Path) -> None:
    result = runner.invoke(app, ["split", "--source", str(tmp_path / "missing")])
    assert "0 files written" in result.output


def test_split_with_openai_source(tmp_path: Path) -> None:
    source = tmp_path / "export"
    source.mkdir()
    payload = {
        "mapping": {
            "node1": {
                "message": {
                    "id": "msg1",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Hello"]},
                    "create_time": 1700000000.0,
                },
                "children": [],
            }
        },
        "title": "Test Chat",
        "create_time": 1700000000.0,
    }
    (source / "convs.json").write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "out"

    result = runner.invoke(
        app, ["split", "--source", str(source), "--output", str(output)]
    )
    assert result.exit_code == 0
    assert "files written" in result.output


def test_search_missing_dir() -> None:
    result = runner.invoke(app, ["search", "test", "--conversations", "/nonexistent/dir"])
    assert result.exit_code == 1
    assert "not found" in result.output


@patch("mem0ry.conversations.search.search", return_value=[])
def test_search_no_results(mock_search: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    result = runner.invoke(
        app, ["search", "python", "--conversations", str(tmp_path)]
    )
    assert "Nenhum resultado" in result.output


@patch("mem0ry.conversations.search.search")
def test_search_with_results(mock_search: MagicMock, tmp_path: Path) -> None:
    md = tmp_path / "2026-04-21" / "python.md"
    md.parent.mkdir(parents=True)
    md.write_text("Python stuff", encoding="utf-8")
    mock_search.return_value = [md]

    result = runner.invoke(
        app, ["search", "python", "--conversations", str(tmp_path)]
    )
    assert "1 resultados" in result.output


def test_benchmark_missing_dir() -> None:
    result = runner.invoke(app, ["benchmark", "test", "--conversations", "/nonexistent/dir"])
    assert result.exit_code == 1


@patch("mem0ry.conversations.benchmark.run_benchmark")
def test_benchmark_with_results(mock_bench: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    mock_bench.return_value = [
        {"backend": "ripgrep", "time_ms": 10.0, "n_files": 1, "paths": [Path("test.md")]},
    ]
    result = runner.invoke(
        app, ["benchmark", "python", "--conversations", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "ripgrep" in result.output


def test_dataset_missing_source(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["dataset", "--source", str(tmp_path / "missing"), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 0
    assert "Dataset built" in result.output


@patch("mem0ry.cli.main.build_bm25_index")
@patch("mem0ry.cli.main.build_fts_index")
def test_index_command(mock_fts: MagicMock, mock_bm25: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    result = runner.invoke(
        app, ["index", "--conversations", str(tmp_path)]
    )
    assert result.exit_code == 0
    mock_bm25.assert_called_once()
    mock_fts.assert_called_once()


@patch("mem0ry.cli.main.build_bm25_index")
def test_index_bm25_only(mock_bm25: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    result = runner.invoke(
        app, ["index", "--backend", "bm25", "--conversations", str(tmp_path)]
    )
    assert result.exit_code == 0
    mock_bm25.assert_called_once()


@patch("mem0ry.cli.main.build_fts_index")
def test_index_fts5_only(mock_fts: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    result = runner.invoke(
        app, ["index", "--backend", "fts5", "--conversations", str(tmp_path)]
    )
    assert result.exit_code == 0
    mock_fts.assert_called_once()


def test_index_missing_dir() -> None:
    result = runner.invoke(
        app, ["index", "--conversations", "/nonexistent/dir"]
    )
    assert result.exit_code == 1
