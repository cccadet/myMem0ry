"""Tests for parsers.gemini — Google Takeout export parsing."""

from __future__ import annotations

import json
from pathlib import Path

from mem0ry.parsers.gemini import GeminiParser, _strip_html


def test_strip_html_simple() -> None:
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_entities() -> None:
    assert _strip_html("a &amp; b") == "a & b"


def test_parse_gemini_entry(tmp_path: Path) -> None:
    payload = [
        {
            "title": "Prompted What is Python?",
            "time": "2026-04-03T14:06:31.934Z",
            "safeHtmlItem": [{"html": "<p>Python is a programming language.</p>"}],
        }
    ]
    path = tmp_path / "activity.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = GeminiParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert convs[0].messages[0].role == "user"
    assert convs[0].messages[0].content == "What is Python?"
    assert convs[0].messages[1].role == "assistant"
    assert "programming language" in convs[0].messages[1].content


def test_parse_skips_empty_entries(tmp_path: Path) -> None:
    payload = [{"title": "No content here", "safeHtmlItem": []}]
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = GeminiParser()
    convs = parser.parse(path)
    assert len(convs) == 0


def test_parse_directory_multiple_files(tmp_path: Path) -> None:
    for name in ["a.json", "b.json"]:
        (tmp_path / name).write_text(
            json.dumps([
                {
                    "title": "Prompted test",
                    "time": "2026-01-01T00:00:00Z",
                    "safeHtmlItem": [{"html": "response"}],
                }
            ]),
            encoding="utf-8",
        )

    parser = GeminiParser()
    convs = parser.parse_directory(tmp_path)
    assert len(convs) == 2
