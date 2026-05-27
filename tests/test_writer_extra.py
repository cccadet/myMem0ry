"""Tests for conversations.writer — format, classify, and split with parsers."""

from __future__ import annotations

import json
from pathlib import Path

from mem0ry.conversations.writer import (
    _format_conversation,
    _classify_payload,
    _is_gemini_list,
    _is_openai_dict,
    _is_openai_list,
    _detect_source_type,
    split_conversations,
)
from mem0ry.parsers.base import ParsedConversation, ParsedMessage


def _make_conv(
    messages: list[tuple[str, str]] | None = None,
    conv_id: str = "c1",
    title: str | None = "Title",
    create_time: str | None = "1700000000.0",
) -> ParsedConversation:
    return ParsedConversation(
        conversation_id=conv_id,
        title=title,
        create_time=create_time,
        messages=[ParsedMessage(role=r, content=c) for r, c in (messages or [])],
    )


def test_format_conversation_with_title() -> None:
    conv = _make_conv([("user", "Hello"), ("assistant", "Hi")])
    result = _format_conversation(conv)
    assert "# Title" in result
    assert "[user]: Hello" in result
    assert "[assistant]: Hi" in result


def test_format_conversation_no_title() -> None:
    conv = _make_conv([], title=None)
    result = _format_conversation(conv)
    assert "# Untitled" in result


def test_format_conversation_no_create_time() -> None:
    conv = _make_conv([], create_time=None)
    result = _format_conversation(conv)
    assert "date:" not in result


def test_format_conversation_with_create_time() -> None:
    conv = _make_conv([], create_time="1700000000.0")
    result = _format_conversation(conv)
    assert "date:" in result


def test_classify_payload_gemini() -> None:
    assert _classify_payload([{"safeHtmlItem": []}]) == "gemini"


def test_classify_payload_openai_dict_conversations() -> None:
    assert _classify_payload({"conversations": []}) == "openai"


def test_classify_payload_openai_dict_mapping() -> None:
    assert _classify_payload({"mapping": {}}) == "openai"


def test_classify_payload_openai_list() -> None:
    assert _classify_payload([{"mapping": {}}]) == "openai"


def test_classify_payload_unknown() -> None:
    assert _classify_payload({"other": "data"}) is None


def test_classify_payload_empty_list() -> None:
    assert _classify_payload([]) is None


def test_is_gemini_list_true() -> None:
    assert _is_gemini_list([{"safeHtmlItem": []}]) is True


def test_is_gemini_list_false() -> None:
    assert _is_gemini_list([{"other": []}]) is False


def test_is_gemini_list_empty() -> None:
    assert _is_gemini_list([]) is False


def test_is_openai_dict_true_conversations() -> None:
    assert _is_openai_dict({"conversations": []}) is True


def test_is_openai_dict_true_mapping() -> None:
    assert _is_openai_dict({"mapping": {}}) is True


def test_is_openai_dict_false() -> None:
    assert _is_openai_dict({"other": 1}) is False


def test_is_openai_list_true() -> None:
    assert _is_openai_list([{"mapping": {}}]) is True


def test_is_openai_list_false() -> None:
    assert _is_openai_list([{"other": 1}]) is False


def test_is_openai_list_empty() -> None:
    assert _is_openai_list([]) is False


def test_detect_source_type_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text("not valid json{{{", encoding="utf-8")
    assert _detect_source_type(tmp_path) is None


def test_detect_source_type_unknown_structure(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text(
        json.dumps({"unknown_key": []}), encoding="utf-8"
    )
    assert _detect_source_type(tmp_path) is None


def test_split_conversations_skips_empty_messages(tmp_path: Path) -> None:
    source = tmp_path / "export"
    source.mkdir()
    payload = [
        {
            "mapping": {
                "node1": {
                    "message": {
                        "id": "m1",
                        "author": {"role": "system"},
                        "content": {"content_type": "text", "parts": ["System prompt"]},
                        "create_time": 1700000000.0,
                    },
                    "children": [],
                }
            },
            "title": "System Only",
            "create_time": 1700000000.0,
        }
    ]
    (source / "convs.json").write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "out"
    stats = split_conversations(source, output, source_type="openai")
    assert stats["total"] == 0


def test_split_conversations_unknown_source_type(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir()
    with open(source / "data.txt", "w") as f:
        f.write("not json")
    try:
        split_conversations(source, tmp_path / "out2")
        assert False, "Should have raised"
    except ValueError as e:
        assert "Could not detect" in str(e)


def test_split_conversations_dedup_filenames(tmp_path: Path) -> None:
    source = tmp_path / "export2"
    source.mkdir()
    payload = [
        {
            "mapping": {
                "n1": {
                    "message": {
                        "id": "m1",
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["Hello"]},
                        "create_time": 1700000000.0,
                    },
                    "children": [],
                }
            },
            "title": "Same Title",
            "create_time": 1700000000.0,
        },
        {
            "mapping": {
                "n2": {
                    "message": {
                        "id": "m2",
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["World"]},
                        "create_time": 1700000000.0,
                    },
                    "children": [],
                }
            },
            "title": "Same Title",
            "create_time": 1700000000.0,
        },
    ]
    (source / "convs.json").write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "out3"
    stats = split_conversations(source, output, source_type="openai")
    assert stats["written"] == 2
