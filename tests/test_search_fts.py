"""Tests for conversations.search_fts — SQLite FTS5 indexing and search."""

from __future__ import annotations

from pathlib import Path

from mem0ry.conversations.search_fts import (
    _db_path,
    build_fts_index,
    search_fts,
)


def test_db_path(tmp_path: Path) -> None:
    result = _db_path(tmp_path)
    assert result == tmp_path / ".fts5_index.db"


def test_build_fts_index_creates_db(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("Python programming", encoding="utf-8")
    build_fts_index(tmp_path)
    assert _db_path(tmp_path).exists()


def test_build_fts_index_empty_dir(tmp_path: Path) -> None:
    build_fts_index(tmp_path)
    assert _db_path(tmp_path).exists()


def test_search_fts_returns_results(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "python.md").write_text(
        "Python programming language", encoding="utf-8"
    )
    (tmp_path / "2026-04-21" / "other.md").write_text(
        "Cooking recipes and food", encoding="utf-8"
    )
    build_fts_index(tmp_path)
    results = search_fts("python", tmp_path, top_k=5)
    assert len(results) >= 1
    assert any("python" in p.name for p in results)


def test_search_fts_builds_index_if_missing(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("unique searchable content", encoding="utf-8")
    assert not _db_path(tmp_path).exists()
    results = search_fts("unique", tmp_path)
    assert _db_path(tmp_path).exists()


def test_search_fts_stopwords_only(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("content", encoding="utf-8")
    build_fts_index(tmp_path)
    results = search_fts("como uma", tmp_path)
    assert results == []


def test_search_fts_no_match(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("hello world", encoding="utf-8")
    build_fts_index(tmp_path)
    results = search_fts("zzzzzznonexistent", tmp_path)
    assert results == []
