"""Cloud mem0 sink that delegates to MemoryClient."""
from __future__ import annotations

from typing import Optional

from mem0.client.main import MemoryClient

from ..config import Settings
from ..domain.models import Conversation
from .base import BaseSink


class Mem0CloudSink(BaseSink):
    """Stores conversations in the mem0 cloud via the official client."""

    def __init__(self, *, settings: Settings | None = None, client: Optional[MemoryClient] = None) -> None:
        settings = settings or Settings()
        super().__init__(default_user_id=settings.default_user_id)

        if client is not None:
            self.client = client
        else:
            self.client = MemoryClient(
                api_key=settings.mem0_api_key,
                host=settings.mem0_host,
                org_id=settings.mem0_org_id,
                project_id=settings.mem0_project_id,
            )

    def store(self, conversation: Conversation, *, user_id: str | None = None) -> dict:
        messages, metadata = self._prepare_payload(conversation)
        return self.client.add(
            messages,
            user_id=self._resolve_user_id(user_id),
            metadata=metadata,
        )
