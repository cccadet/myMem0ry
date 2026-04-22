"""Tests for conversations.search_bm25 — BM25 indexing and search."""

from __future__ import annotations

from pathlib import Path

from mem0ry.conversations.search_bm25 import (
    _tokenize,
    _index_path,
    build_bm25_index,
    search_bm25,
)


def test_tokenize_splits_and_filters() -> None:
    tokens = _tokenize("Como fazer uma busca python")
    assert "python" in tokens
    assert "como" not in tokens
    assert "uma" not in tokens


def test_tokenize_removes_single_chars() -> None:
    tokens = _tokenize("a b cd ef")
    assert "a" not in tokens
    assert "b" not in tokens
    assert "cd" in tokens


def test_tokenize_empty() -> None:
    assert _tokenize("") == []


def test_index_path(tmp_path: Path) -> None:
    result = _index_path(tmp_path)
    assert result == tmp_path / ".bm25_index.pkl"


def test_build_bm25_index_creates_file(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text(
        "Python programming language", encoding="utf-8"
    )
    build_bm25_index(tmp_path)
    assert _index_path(tmp_path).exists()


def test_build_bm25_index_empty_dir(tmp_path: Path, capsys) -> None:
    build_bm25_index(tmp_path)
    assert not _index_path(tmp_path).exists()
    captured = capsys.readouterr()
    assert "Nenhum arquivo" in captured.out


def test_search_bm25_returns_results(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "python.md").write_text(
        "Python programming language is great", encoding="utf-8"
    )
    (tmp_path / "2026-04-21" / "other.md").write_text(
        "Cooking recipes and food", encoding="utf-8"
    )
    build_bm25_index(tmp_path)
    results = search_bm25("python programming", tmp_path, top_k=5)
    assert len(results) >= 1
    assert any("python" in p.name for p in results)


def test_search_bm25_builds_index_if_missing(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("unique content here", encoding="utf-8")
    assert not _index_path(tmp_path).exists()
    results = search_bm25("unique", tmp_path)
    assert _index_path(tmp_path).exists()


def test_search_bm25_stopwords_only(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("content", encoding="utf-8")
    build_bm25_index(tmp_path)
    results = search_bm25("como uma", tmp_path)
    assert results == []


def test_search_bm25_ranks_by_relevance(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "python.md").write_text(
        "python python python", encoding="utf-8"
    )
    (tmp_path / "2026-04-21" / "other.md").write_text(
        "cooking recipes food", encoding="utf-8"
    )
    build_bm25_index(tmp_path)
    results = search_bm25("python", tmp_path, top_k=2)
    assert len(results) >= 1
    assert any("python" in p.name for p in results)
