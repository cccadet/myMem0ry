"""Tests for dataset.temporal — build_temporal_system_prompt."""

from __future__ import annotations

from mem0ry.dataset.temporal import build_temporal_system_prompt
from mem0ry.parsers.base import ParsedConversation


def test_build_temporal_prompt_with_timestamp() -> None:
    conv = ParsedConversation(
        conversation_id="1", title="Chat", create_time="1700000000.0", messages=[]
    )
    result = build_temporal_system_prompt(conv, "Be helpful.")
    assert "Be helpful." in result
    assert "conversation took place on" in result


def test_build_temporal_prompt_with_title() -> None:
    conv = ParsedConversation(
        conversation_id="1", title="My Chat", create_time="1700000000.0", messages=[]
    )
    result = build_temporal_system_prompt(conv, "Be helpful.")
    assert 'title is: "My Chat"' in result


def test_build_temporal_prompt_no_timestamp() -> None:
    conv = ParsedConversation(
        conversation_id="1", title="No Time", create_time=None, messages=[]
    )
    result = build_temporal_system_prompt(conv, "Be helpful.")
    assert "conversation took place" not in result
    assert "Be helpful." in result


def test_build_temporal_prompt_no_title() -> None:
    conv = ParsedConversation(
        conversation_id="1", title=None, create_time="1700000000.0", messages=[]
    )
    result = build_temporal_system_prompt(conv, "Be helpful.")
    assert "title is" not in result


def test_build_temporal_prompt_strips_newlines_in_title() -> None:
    conv = ParsedConversation(
        conversation_id="1", title="Line1\nLine2", create_time=None, messages=[]
    )
    build_temporal_system_prompt(conv, "test")
    assert "\n" not in conv.title.replace("\n", " ")


def test_build_temporal_prompt_empty_title() -> None:
    conv = ParsedConversation(
        conversation_id="1", title="  ", create_time=None, messages=[]
    )
    result = build_temporal_system_prompt(conv, "Be helpful.")
    assert "title is" not in result
