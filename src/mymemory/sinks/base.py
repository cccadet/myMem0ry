"""Abstract sink helpers shared between different mem0 transports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from mymemory.domain.models import Conversation, Message


class BaseSink(ABC):
    """Common helpers shared by every sink implementation."""

    def __init__(self, default_user_id: str | None = None) -> None:
        self.default_user_id = default_user_id

    @abstractmethod
    def store(self, conversation: Conversation, *, user_id: str | None = None) -> Any:
        """Persist the conversation in the configured sink."""

    def _resolve_user_id(self, user_id: str | None) -> str:
        identifier = user_id or self.default_user_id
        if not identifier:
            raise ValueError("user_id is required to persist memories")
        return identifier

    def _prepare_payload(self, conversation: Conversation) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        messages = self._build_messages(conversation.messages)
        metadata = self._build_metadata(conversation)
        return messages, metadata

    def _build_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        payload = []
        for message in messages:
            data: Dict[str, Any] = {
                "role": message.role,
                "content": message.content,
                "metadata": self._build_message_metadata(message),
            }
            created_at = self._isoformat(message.created_at)
            if created_at:
                data["created_at"] = created_at
            payload.append(data)
        return payload

    @staticmethod
    def _build_message_metadata(message: Message) -> Dict[str, Any]:
        metadata = dict(message.metadata)
        if message.source_message_id:
            metadata["source_message_id"] = message.source_message_id
        return metadata

    def _build_metadata(self, conversation: Conversation) -> Dict[str, Any]:
        metadata = dict(conversation.metadata)
        metadata.update(
            conversation_id=conversation.id,
            source_provider=conversation.source.value,
            source_conversation_id=conversation.source_conversation_id,
            message_count=len(conversation.messages),
            participants=conversation.participants,
        )

        created_at = self._isoformat(conversation.created_at)
        updated_at = self._isoformat(conversation.updated_at)
        if created_at:
            metadata["conversation_created_at"] = created_at
        if updated_at:
            metadata["conversation_updated_at"] = updated_at

        return metadata

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        if not value:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
