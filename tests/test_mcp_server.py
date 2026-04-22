"""Tests for mcp_server — validation, writing, preview, and tool logic."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from mem0ry.mcp_server import (
    _validate_date,
    _resolve_within,
    _write_md,
    _preview_text,
    _conversations_dir,
    log_message,
    save_memory,
    save_conversation,
    read_memory,
    auto_save_instructions,
    conversation_logger,
)
from mem0ry.mcp_server import _session_id, _session_title


def test_validate_date_valid() -> None:
    assert _validate_date("2026-04-21") == "2026-04-21"


def test_validate_date_invalid_format() -> None:
    with pytest.raises(ValueError, match="Invalid date format"):
        _validate_date("21-04-2026")


def test_validate_date_empty() -> None:
    with pytest.raises(ValueError, match="Invalid date format"):
        _validate_date("")


def test_validate_date_partial() -> None:
    with pytest.raises(ValueError, match="Invalid date format"):
        _validate_date("2026-04")


def test_resolve_within_valid(tmp_path: Path) -> None:
    result = _resolve_within(tmp_path, "2026-04-21", "test.md")
    assert result == tmp_path / "2026-04-21" / "test.md"


def test_resolve_within_traversal_blocked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Path traversal blocked"):
        _resolve_within(tmp_path, "..", "etc", "passwd")


def test_resolve_within_dotdot_escaped(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Path traversal blocked"):
        _resolve_within(tmp_path, "../../tmp")


def test_write_md_creates_file(tmp_path: Path) -> None:
    path = _write_md(tmp_path, "2026-04-21", "Test Title", "Hello world")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "# Test Title" in text
    assert "Hello world" in text
    assert "date: 2026-04-21" in text


def test_write_md_creates_date_subdir(tmp_path: Path) -> None:
    _write_md(tmp_path, "2026-01-15", "X", "Y")
    assert (tmp_path / "2026-01-15").is_dir()


def test_write_md_unique_ids(tmp_path: Path) -> None:
    p1 = _write_md(tmp_path, "2026-01-01", "A", "a")
    p2 = _write_md(tmp_path, "2026-01-01", "B", "b")
    assert p1.name != p2.name


def test_preview_text_normal(tmp_path: Path) -> None:
    f = tmp_path / "test.md"
    f.write_text("line1\nline2\nline3\nline4\nline5\nline6", encoding="utf-8")
    result = _preview_text(f)
    assert "line1" in result
    assert "line6" not in result


def test_preview_text_truncates_long(tmp_path: Path) -> None:
    long_line = "x" * 200
    f = tmp_path / "big.md"
    f.write_text("\n".join([long_line] * 10), encoding="utf-8")
    result = _preview_text(f)
    assert len(result) <= 503
    assert result.endswith("...")


def test_preview_text_missing_file(tmp_path: Path) -> None:
    result = _preview_text(tmp_path / "nonexistent.md")
    assert result == ""


def test_conversations_dir_returns_path() -> None:
    result = _conversations_dir()
    assert isinstance(result, Path)


def test_log_message_creates_file(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    old_sid, old_title = mod._session_id, mod._session_title
    try:
        mod._session_id = None
        mod._session_title = "test-session"
        with patch.object(mod, "_conversations_dir", return_value=tmp_path):
            result = log_message("user", "hello world")
        assert "Logged (user)" in result
        today = date.today().isoformat()
        files = list((tmp_path / today).glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "[user]: hello world" in content
    finally:
        mod._session_id, mod._session_title = old_sid, old_title


def test_log_message_appends_to_existing(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    old_sid, old_title = mod._session_id, mod._session_title
    try:
        mod._session_id = None
        mod._session_title = "append-test"
        with patch.object(mod, "_conversations_dir", return_value=tmp_path):
            log_message("user", "first")
            log_message("assistant", "second")
        today = date.today().isoformat()
        files = list((tmp_path / today).glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "[user]: first" in content
        assert "[assistant]: second" in content
    finally:
        mod._session_id, mod._session_title = old_sid, old_title


def test_save_memory_creates_file(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        result = save_memory("My Note", "Important stuff", dt="2026-04-21")
    assert "Saved:" in result
    assert (tmp_path / "2026-04-21").is_dir()
    files = list((tmp_path / "2026-04-21").glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# My Note" in content
    assert "Important stuff" in content


def test_save_memory_invalid_date(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        with pytest.raises(ValueError, match="Invalid date format"):
            save_memory("X", "Y", dt="bad-date")


def test_save_conversation_creates_file(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a language."},
    ]
    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        result = save_conversation("Python Chat", messages, dt="2026-04-21")
    assert "Saved:" in result
    files = list((tmp_path / "2026-04-21").glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "[user]: What is Python?" in content
    assert "[assistant]: Python is a language." in content


def test_save_conversation_defaults_role(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    messages = [{"content": "no role field"}]
    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        save_conversation("NoRole", messages, dt="2026-01-01")
    files = list((tmp_path / "2026-01-01").glob("*.md"))
    content = files[0].read_text(encoding="utf-8")
    assert "[user]: no role field" in content


def test_read_memory_valid(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    (tmp_path / "2026-04-21").mkdir()
    (tmp_path / "2026-04-21" / "test.md").write_text("content here", encoding="utf-8")
    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        result = read_memory("2026-04-21/test.md")
    assert result == "content here"


def test_read_memory_not_found(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        result = read_memory("2026-04-21/nonexistent.md")
    assert "File not found" in result


def test_read_memory_traversal(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_conversations_dir", return_value=tmp_path):
        result = read_memory("../../etc/passwd")
    assert result == "Invalid path"


def test_auto_save_instructions_returns_string() -> None:
    result = auto_save_instructions()
    assert "log_message" in result
    assert "MANDATORY" in result


def test_conversation_logger_with_topic() -> None:
    result = conversation_logger(topic="testing")
    assert "testing" in result
    assert "log_message" in result


def test_conversation_logger_without_topic() -> None:
    result = conversation_logger()
    assert "Conversation topic" not in result
    assert "log_message" in result
