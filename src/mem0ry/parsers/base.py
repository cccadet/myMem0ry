"""Canonical parser interfaces for OpenAI exports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedMessage:
    """Normalized message extracted from the export."""

    role: str
    content: str
    created_at: str | None = None
    message_id: str | None = None


@dataclass
class ParsedConversation:
    """In-memory representation of a single OpenAI conversation."""

    conversation_id: str
    title: str | None
    create_time: str | None
    messages: list[ParsedMessage] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


class BaseParser(ABC):
    """Base hook for parsers that consume export files."""

    @abstractmethod
    def parse(self, path: Path) -> list[ParsedConversation]:
        """Parse a single export file into normalized conversations."""

    def parse_directory(self, directory: Path) -> list[ParsedConversation]:
        """Parse all JSON files in a directory, returning every conversation."""
        conversations: list[ParsedConversation] = []
        for entry in sorted(directory.glob("*.json")):
            conversations.extend(self.parse(entry))
        return conversations
