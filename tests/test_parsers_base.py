"""Tests for parsers.base — data structures and BaseParser ABC."""

from __future__ import annotations

from pathlib import Path

from mem0ry.parsers.base import BaseParser, ParsedConversation, ParsedMessage


def test_parsed_message_defaults() -> None:
    msg = ParsedMessage(role="user", content="hello")
    assert msg.created_at is None
    assert msg.message_id is None


def test_parsed_conversation_defaults() -> None:
    conv = ParsedConversation(
        conversation_id="abc", title="Test", create_time="1234.5"
    )
    assert conv.messages == []
    assert conv.metadata == {}


def test_base_parser_is_abstract() -> None:
    import abc

    assert abc.ABC in BaseParser.__bases__


def test_base_parser_parse_directory(tmp_path: Path) -> None:
    class FakeParser(BaseParser):
        def parse(self, path: Path) -> list[ParsedConversation]:
            return [
                ParsedConversation(
                    conversation_id="test",
                    title="fake",
                    create_time=None,
                    messages=[ParsedMessage(role="user", content="hi")],
                )
            ]

    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.json").write_text("{}")

    parser = FakeParser()
    results = parser.parse_directory(tmp_path)
    assert len(results) == 2
