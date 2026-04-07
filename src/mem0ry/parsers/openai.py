"""Parser for OpenAI export JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BaseParser, ParsedConversation, ParsedMessage


class OpenAIParser(BaseParser):
    """Normalize ChatGPT exports into chronological conversations."""

    _allowed_roles = {"user", "assistant"}

    def parse(self, path: Path) -> list[ParsedConversation]:
        with open(path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)

        conversations: list[ParsedConversation] = []
        entries = []
        if isinstance(payload, dict):
            entries = payload.get("conversations", [])
        elif isinstance(payload, list):
            entries = payload
        else:
            entries = []

        for raw in entries:
            mapping = raw.get("mapping", {}) or {}
            if not mapping:
                continue

            messages: list[ParsedMessage] = []
            root_ids = self._root_nodes(mapping)
            for root_id in root_ids:
                self._walk(mapping, root_id, messages)

            if not messages:
                continue

            conversations.append(
                ParsedConversation(
                    conversation_id=raw.get("id")
                    or raw.get("conversation_id")
                    or raw.get("title", ""),
                    title=raw.get("title"),
                    create_time=raw.get("create_time"),
                    messages=messages,
                    metadata={"source_file": path.name},
                )
            )

        return conversations

    def _root_nodes(self, mapping: dict[str, Any]) -> list[str]:
        children = {
            child for node in mapping.values() for child in node.get("children", [])
        }
        return [node_id for node_id in mapping if node_id not in children]

    def _walk(
        self, mapping: dict[str, Any], node_id: str, output: list[ParsedMessage]
    ) -> None:
        node = mapping.get(node_id)
        if not node:
            return

        message = node.get("message")
        if message:
            role = message.get("author", {}).get("role")
            if role in self._allowed_roles:
                content = self._merge_parts(message)
                if content.strip():
                    output.append(
                        ParsedMessage(
                            role=role,
                            content=content.strip(),
                            created_at=message.get("create_time"),
                            message_id=message.get("id") or node_id,
                        )
                    )

        for child_id in node.get("children", []):
            self._walk(mapping, child_id, output)

    def _merge_parts(self, message: dict[str, Any]) -> str:
        parts = message.get("content", {}).get("parts")
        if isinstance(parts, list):
            return "".join(str(part or "") for part in parts)
        fallback = message.get("content", {}).get("text")
        return str(fallback or "")
