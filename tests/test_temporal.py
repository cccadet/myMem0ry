"""Tests for dataset.temporal — timestamp formatting and enrichment."""

from __future__ import annotations

from mem0ry.dataset.temporal import enrich_conversations, format_timestamp
from mem0ry.parsers.base import ParsedConversation


def test_format_timestamp_unix() -> None:
    result = format_timestamp("1700000000.0")
    assert result is not None
    assert "2023" in result


def test_format_timestamp_iso() -> None:
    result = format_timestamp("2026-04-03T14:06:31.934Z")
    assert result is not None
    assert "2026" in result


def test_format_timestamp_none() -> None:
    assert format_timestamp(None) is None


def test_format_timestamp_invalid() -> None:
    assert format_timestamp("not-a-date") is None


def test_enrich_conversations_sorts_by_time() -> None:
    convs = [
        ParsedConversation(conversation_id="b", title="B", create_time="2000000.0"),
        ParsedConversation(conversation_id="a", title="A", create_time="1000000.0"),
        ParsedConversation(conversation_id="c", title="C", create_time=None),
    ]
    sorted_convs = enrich_conversations(convs)
    assert sorted_convs[0].conversation_id == "c"
    assert sorted_convs[1].conversation_id == "a"
    assert sorted_convs[2].conversation_id == "b"
