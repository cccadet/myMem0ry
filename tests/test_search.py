"""Tests for conversations.search — ripgrep keyword extraction."""

from __future__ import annotations

from mem0ry.conversations.search import _extract_keywords


def test_extract_keywords_simple() -> None:
    result = _extract_keywords("python programming")
    assert "python" in result
    assert "programming" in result


def test_extract_keywords_strips_stop_words() -> None:
    result = _extract_keywords("como fazer uma busca")
    assert "como" not in result
    assert "uma" not in result
    assert "busca" in result


def test_extract_keywords_strips_single_chars() -> None:
    result = _extract_keywords("a b cd")
    assert "a" not in result
    assert "b" not in result
    assert "cd" in result


def test_extract_keywords_empty() -> None:
    assert _extract_keywords("") == []


def test_extract_keywords_portuguese_accents() -> None:
    result = _extract_keywords("informação aplicação")
    assert "informação" in result
    assert "aplicação" in result
