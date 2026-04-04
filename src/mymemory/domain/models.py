from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import SourceProvider


@dataclass
class Message:
    source_message_id: str | None
    role: str
    content: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    id: str
    source: SourceProvider
    source_conversation_id: str
    title: str | None = None
    participants: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
