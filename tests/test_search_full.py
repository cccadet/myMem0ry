"""Tests for conversations.search — ripgrep search and _check_rg."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mem0ry.conversations.search import search, _check_rg, _extract_keywords


def test_check_rg_raises_when_missing() -> None:
    with patch("mem0ry.conversations.search.shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError, match="ripgrep"):
            _check_rg()


def test_check_rg_passes_when_found() -> None:
    with patch("mem0ry.conversations.search.shutil.which", return_value="/usr/bin/rg"):
        _check_rg()


def test_search_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    result = search("python", tmp_path / "nonexistent")
    assert result == []


def test_search_returns_empty_for_stopwords_only(tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    result = search("como uma", tmp_path)
    assert result == []


def test_search_with_ripgrep(tmp_path: Path) -> None:
    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "python.md").write_text(
        "Python programming language", encoding="utf-8"
    )
    (tmp_path / "2026-04-21" / "other.md").write_text(
        "Unrelated content", encoding="utf-8"
    )
    result = search("python", tmp_path, top_k=5)
    assert len(result) >= 1
    assert any("python" in p.name for p in result)


def test_search_no_matches(tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("hello world", encoding="utf-8")
    result = search("zzzzzznonexistent", tmp_path)
    assert result == []
