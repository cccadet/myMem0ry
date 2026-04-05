"""Local mem0 sink implementation using the bundled Memory class."""
from __future__ import annotations

from typing import Optional

from mem0.memory.main import Memory

from ..config import Settings
from ..domain.models import Conversation
from .base import BaseSink


class Mem0LocalSink(BaseSink):
    """Stores conversations in a local mem0 instance."""

    def __init__(self, *, settings: Settings | None = None, memory: Optional[Memory] = None) -> None:
        settings = settings or Settings()
        super().__init__(default_user_id=settings.default_user_id)

        config = settings.local_memory_config()
        if memory is not None:
            self.memory = memory
        elif config:
            self.memory = Memory.from_config(config)
        else:
            self.memory = Memory()

    def store(self, conversation: Conversation, *, user_id: str | None = None) -> dict:
        messages, metadata = self._prepare_payload(conversation)
        return self.memory.add(
            messages,
            user_id=self._resolve_user_id(user_id),
            metadata=metadata,
        )
