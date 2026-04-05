from __future__ import annotations

from datetime import datetime, timezone

from mymemory.config import Settings
from mymemory.domain.enums import SourceProvider
from mymemory.domain.models import Conversation, Message
from mymemory.sinks.mem0_local import Mem0LocalSink


class DummyMemory:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, messages, *, user_id, metadata, **kwargs) -> dict:
        self.calls.append(
            {
                "messages": messages,
                "user_id": user_id,
                "metadata": metadata,
                "kwargs": kwargs,
            }
        )
        return {"status": "ok", "messages": messages}


def _conversation() -> Conversation:
    now = datetime.now(timezone.utc)
    message = Message(
        source_message_id="msg-1",
        role="assistant",
        content="Response",
        created_at=now,
        metadata={"foo": "bar"},
    )
    return Conversation(
        id="conv-1",
        source=SourceProvider.CLAUDE,
        source_conversation_id="src-1",
        participants=["alice", "assistant"],
        messages=[message],
        created_at=now,
        updated_at=now,
        metadata={"imported_at": "2025-01-01T00:00:00Z"},
    )


def test_mem0_local_sink_builds_payload() -> None:
    memory = DummyMemory()
    sink = Mem0LocalSink(memory=memory, settings=Settings(default_user_id="tester"))

    result = sink.store(_conversation(), user_id="tester")

    assert result["status"] == "ok"
    assert len(memory.calls) == 1
    calling = memory.calls[0]
    assert calling["user_id"] == "tester"
    assert calling["metadata"]["conversation_id"] == "conv-1"
    assert calling["metadata"]["message_count"] == 1
    assert calling["messages"][0]["metadata"]["source_message_id"] == "msg-1"


def test_mem0_local_sink_uses_default_user() -> None:
    memory = DummyMemory()
    sink = Mem0LocalSink(memory=memory, settings=Settings(default_user_id="default"))

    sink.store(_conversation())

    assert memory.calls[0]["user_id"] == "default"
