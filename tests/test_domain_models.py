from __future__ import annotations

from datetime import datetime, timezone

from mymemory.domain.enums import IngestionMode, SinkTarget, SourceProvider
from mymemory.domain.models import Conversation, Message


def test_conversation_schema_roundtrip() -> None:
    created = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    message = Message(
        source_message_id="msg-123",
        role="user",
        content="Hello?",
        created_at=created,
        metadata={"intent": "greeting"},
    )

    conversation = Conversation(
        id="conv-abc",
        source=SourceProvider.CHATGPT,
        source_conversation_id="source-123",
        title="Greeting thread",
        participants=["alice", "assistant"],
        messages=[message],
        created_at=created,
        updated_at=created,
        metadata={"source_provider": SourceProvider.CHATGPT.value},
    )

    assert conversation.source == SourceProvider.CHATGPT
    assert conversation.metadata["source_provider"] == "chatgpt"
    assert conversation.messages[0].content == "Hello?"
    assert conversation.messages[0].created_at == created


def test_default_collections_are_isolated() -> None:
    base_kwargs = dict(
        id="any",
        source=SourceProvider.GEMINI,
        source_conversation_id="src",
    )

    first = Conversation(**base_kwargs)
    second = Conversation(**base_kwargs)

    first.participants.append("alice")
    first.messages.append(
        Message(
            source_message_id=None,
            role="assistant",
            content="Reply",
            created_at=datetime.now(timezone.utc),
        )
    )

    assert second.participants == []
    assert second.messages == []


def test_enums_cover_expected_modes() -> None:
    assert SourceProvider.CLAUDE.value == "claude"
    assert SinkTarget.LOCAL.value == "local"
    assert SinkTarget.CLOUD.value == "cloud"
    assert IngestionMode.MESSAGE.value == "message"
    assert IngestionMode.CONVERSATION.value == "conversation"
