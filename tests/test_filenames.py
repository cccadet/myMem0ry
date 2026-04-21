"""Tests for utils.filenames — shared filename sanitization."""

from __future__ import annotations

from mem0ry.utils.filenames import sanitize_title


def test_sanitize_normal_string() -> None:
    assert sanitize_title("hello world") == "hello world"


def test_sanitize_strips_slashes() -> None:
    assert sanitize_title("path/to/file") == "pathtofile"


def test_sanitize_strips_special_chars() -> None:
    assert sanitize_title('a:b*c?d"e<f>g|h') == "abcdefgh"


def test_sanitize_truncates_long_title() -> None:
    long_title = "x" * 200
    assert len(sanitize_title(long_title)) == 120


def test_sanitize_empty_becomes_untitled() -> None:
    assert sanitize_title("") == "untitled"
    assert sanitize_title("   ") == "untitled"


def test_sanitize_strips_newlines() -> None:
    assert sanitize_title("hello\nworld") == "hello world"
