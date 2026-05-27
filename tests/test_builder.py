"""Tests for dataset.builder — ChatML example generation."""

from __future__ import annotations

from mem0ry.parsers.base import ParsedConversation, ParsedMessage
from mem0ry.dataset.builder import (
    ChatMLExample,
    build_chatml_examples,
    _resolve_prompt,
    _build_messages,
    _split_messages,
)


def _make_conv(
    messages: list[tuple[str, str]],
    conv_id: str = "test-1",
    title: str | None = "Test",
    create_time: str | None = "1700000000.0",
) -> ParsedConversation:
    return ParsedConversation(
        conversation_id=conv_id,
        title=title,
        create_time=create_time,
        messages=[ParsedMessage(role=r, content=c) for r, c in messages],
    )


def test_build_chatml_examples_basic() -> None:
    conv = _make_conv(
        [
            ("user", "What is Python?"),
            ("assistant", "Python is a programming language."),
        ]
    )
    results = build_chatml_examples(
        [conv], system_prompt="You are helpful.", use_temporal=False
    )
    assert len(results) >= 1
    assert isinstance(results[0], ChatMLExample)
    assert results[0].conversation_id == "test-1"


def test_build_chatml_examples_skips_empty() -> None:
    conv = ParsedConversation(
        conversation_id="empty", title=None, create_time=None, messages=[]
    )
    results = build_chatml_examples([conv])
    assert len(results) == 0


def test_build_chatml_examples_min_turns_filter() -> None:
    conv = _make_conv([("user", "Hi")], conv_id="short")
    results = build_chatml_examples([conv], min_turns=2)
    assert len(results) == 0


def test_build_chatml_examples_metadata() -> None:
    conv = _make_conv(
        [("user", "Hello"), ("assistant", "Hi there")],
        conv_id="meta-test",
        title="Meta",
    )
    results = build_chatml_examples([conv], min_turns=2)
    assert results[0].title == "Meta"
    assert results[0].metadata["conversation_id"] == "meta-test"
    assert results[0].metadata["chunk_index"] == "0"


def test_resolve_prompt_none_base() -> None:
    conv = _make_conv([("user", "hi")])
    assert _resolve_prompt(None, conv, use_temporal=True) is None


def test_resolve_prompt_no_temporal() -> None:
    conv = _make_conv([("user", "hi")])
    result = _resolve_prompt("Be helpful.", conv, use_temporal=False)
    assert result == "Be helpful."


def test_resolve_prompt_with_temporal() -> None:
    conv = _make_conv([("user", "hi")], title="Chat")
    result = _resolve_prompt("Be helpful.", conv, use_temporal=True)
    assert "Be helpful" in result
    assert "conversation took place" in result


def test_build_messages_with_system_prompt() -> None:
    msgs = [ParsedMessage(role="user", content="hi")]
    result = _build_messages(msgs, "system prompt")
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "system prompt"
    assert result[1]["role"] == "user"


def test_build_messages_without_system_prompt() -> None:
    msgs = [ParsedMessage(role="user", content="hi")]
    result = _build_messages(msgs, None)
    assert len(result) == 1
    assert result[0]["role"] == "user"


def test_split_messages_no_split_needed() -> None:
    msgs = [ParsedMessage(role="user", content="short")]
    chunks = _split_messages(msgs, max_chars=10000, overlap_turns=2, min_turns=1)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1


def test_split_messages_splits_long() -> None:
    msgs = [
        ParsedMessage(role="user", content="x" * 100),
        ParsedMessage(role="assistant", content="y" * 100),
        ParsedMessage(role="user", content="z" * 100),
        ParsedMessage(role="assistant", content="w" * 100),
    ]
    chunks = _split_messages(msgs, max_chars=250, overlap_turns=1, min_turns=2)
    assert len(chunks) >= 2


def test_split_messages_discards_short_tail() -> None:
    msgs = [
        ParsedMessage(role="user", content="long enough"),
    ]
    chunks = _split_messages(msgs, max_chars=10000, overlap_turns=0, min_turns=2)
    assert len(chunks) == 0


def test_split_messages_overlap() -> None:
    msgs = [
        ParsedMessage(role="user", content="a" * 80),
        ParsedMessage(role="assistant", content="b" * 80),
        ParsedMessage(role="user", content="c" * 80),
    ]
    chunks = _split_messages(msgs, max_chars=160, overlap_turns=1, min_turns=2)
    if len(chunks) > 1:
        assert chunks[1][0].content.startswith("b")
