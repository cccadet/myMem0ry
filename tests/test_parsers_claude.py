"""Tests for parsers.claude — ClaudeCodeParser and ClaudeExportParser."""

from __future__ import annotations

import json
from pathlib import Path

from mem0ry.parsers.claude import ClaudeCodeParser, ClaudeExportParser


def test_parse_jsonl_single_turn(tmp_path: Path) -> None:
    lines = [
        json.dumps({"type": "human", "message": {"content": "Hello"}, "timestamp": "2025-01-01T00:00:00Z"}),
        json.dumps({"type": "assistant", "message": {"content": "Hi there"}, "timestamp": "2025-01-01T00:00:01Z"}),
    ]
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")

    parser = ClaudeCodeParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert len(convs[0].messages) == 2
    assert convs[0].messages[0].role == "user"
    assert convs[0].messages[0].content == "Hello"
    assert convs[0].messages[1].role == "assistant"


def test_parse_jsonl_with_content_blocks(tmp_path: Path) -> None:
    lines = [
        json.dumps({
            "type": "human",
            "message": {"content": "Question"},
            "timestamp": "2025-06-01T00:00:00Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Part one"},
                    {"type": "text", "text": "Part two"},
                    {"type": "image", "url": "ignored"},
                ]
            },
            "timestamp": "2025-06-01T00:00:01Z",
        }),
    ]
    path = tmp_path / "blocks.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")

    parser = ClaudeCodeParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert "Part one" in convs[0].messages[1].content
    assert "Part two" in convs[0].messages[1].content


def test_parse_jsonl_skips_empty_lines(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("\n\n  \n", encoding="utf-8")

    parser = ClaudeCodeParser()
    convs = parser.parse(path)
    assert convs == []


def test_parse_jsonl_skips_system_messages(tmp_path: Path) -> None:
    lines = [
        json.dumps({"type": "system", "message": {"content": "init"}}),
        json.dumps({"type": "human", "message": {"content": "hi"}}),
    ]
    path = tmp_path / "mixed.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")

    parser = ClaudeCodeParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert len(convs[0].messages) == 1


def test_parse_directory_jsonl(tmp_path: Path) -> None:
    for name in ["a.jsonl", "b.jsonl"]:
        path = tmp_path / name
        path.write_text(
            json.dumps({"type": "human", "message": {"content": "q"}}) + "\n",
            encoding="utf-8",
        )

    parser = ClaudeCodeParser()
    convs = parser.parse_directory(tmp_path)
    assert len(convs) == 2


def test_parse_export_list_format(tmp_path: Path) -> None:
    payload = [
        {
            "uuid": "abc-123",
            "name": "Test Chat",
            "created_at": "2025-01-15T10:00:00Z",
            "chat_messages": [
                {"sender": "human", "text": "What is 2+2?", "created_at": "2025-01-15T10:00:00Z"},
                {"sender": "assistant", "text": "4", "created_at": "2025-01-15T10:00:01Z"},
            ],
        }
    ]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = ClaudeExportParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert convs[0].title == "Test Chat"
    assert len(convs[0].messages) == 2


def test_parse_export_dict_with_conversations(tmp_path: Path) -> None:
    payload = {
        "conversations": [
            {
                "uuid": "def-456",
                "name": "Another",
                "chat_messages": [
                    {"sender": "user", "text": "Hello"},
                    {"sender": "assistant", "text": "World"},
                ],
            }
        ]
    }
    path = tmp_path / "dict_export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = ClaudeExportParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert convs[0].messages[0].role == "user"


def test_parse_export_skips_empty_conversations(tmp_path: Path) -> None:
    payload = [
        {"uuid": "empty", "name": "Empty", "chat_messages": []},
        {
            "uuid": "full",
            "name": "Full",
            "chat_messages": [{"sender": "human", "text": "hi"}],
        },
    ]
    path = tmp_path / "mixed.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = ClaudeExportParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert convs[0].title == "Full"


def test_parse_export_content_blocks(tmp_path: Path) -> None:
    payload = [
        {
            "uuid": "block-1",
            "name": "Blocks",
            "chat_messages": [
                {
                    "sender": "assistant",
                    "content": [
                        {"type": "text", "text": "Answer"},
                        {"type": "code", "text": "skip me"},
                    ],
                },
            ],
        }
    ]
    path = tmp_path / "blocks.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = ClaudeExportParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert "Answer" in convs[0].messages[0].content
