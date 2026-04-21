"""Tests for conversations.writer — conversation splitting and date extraction."""

from __future__ import annotations

import json
from pathlib import Path

from mem0ry.conversations.writer import _extract_date, _detect_source_type, split_conversations


def test_extract_date_unix_timestamp() -> None:
    assert _extract_date("1700000000.0") == "2023-11-14"


def test_extract_date_iso_format() -> None:
    assert _extract_date("2026-04-03T14:06:31.934Z") == "2026-04-03"


def test_extract_date_none() -> None:
    assert _extract_date(None) == "unknown"


def test_extract_date_empty() -> None:
    assert _extract_date("") == "unknown"


def test_extract_date_float() -> None:
    assert _extract_date(1700000000.0) == "2023-11-14"


def test_detect_source_type_gemini(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text(
        json.dumps([{"safeHtmlItem": []}]), encoding="utf-8"
    )
    assert _detect_source_type(tmp_path) == "gemini"


def test_detect_source_type_openai_dict(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text(
        json.dumps({"conversations": []}), encoding="utf-8"
    )
    assert _detect_source_type(tmp_path) == "openai"


def test_detect_source_type_openai_list(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text(
        json.dumps([{"mapping": {}}]), encoding="utf-8"
    )
    assert _detect_source_type(tmp_path) == "openai"


def test_detect_source_type_empty_dir(tmp_path: Path) -> None:
    assert _detect_source_type(tmp_path) is None


def test_split_conversations_unknown_type(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("not json")
    try:
        split_conversations(tmp_path, tmp_path / "out")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Could not detect" in str(e)
