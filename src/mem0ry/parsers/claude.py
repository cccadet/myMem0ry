"""Parser for Claude Code JSONL and claude.ai JSON export files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BaseParser, ParsedConversation, ParsedMessage


class ClaudeCodeParser(BaseParser):
    """Parse Claude Code JSONL exports (~/.claude/projects/*/).

    Each line is a JSON object with fields: type, message, timestamp.
    We group consecutive user/assistant turns into a single conversation
    per file.

    Usage::

        parser = ClaudeCodeParser()
        convs = parser.parse(Path("session.jsonl"))
    """

    def _parse_line(self, line: str) -> ParsedMessage | None:
        line = line.strip()
        if not line:
            return None
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return None

        msg_type = entry.get("type", "")
        # Claude Code live transcripts use "user"; older exports use "human".
        if msg_type not in ("human", "user", "assistant"):
            return None

        content = self._extract_text(entry)
        if not content.strip():
            return None

        return ParsedMessage(
            role="user" if msg_type in ("human", "user") else "assistant",
            content=content.strip(),
            created_at=str(entry.get("timestamp") or entry.get("time") or ""),
            message_id=entry.get("uuid"),
        )

    def parse(self, path: Path) -> list[ParsedConversation]:
        lines = path.read_text(encoding="utf-8").splitlines()

        messages: list[ParsedMessage] = []
        first_ts: str | None = None

        for line in lines:
            msg = self._parse_line(line)
            if msg is None:
                continue
            if first_ts is None and msg.created_at:
                first_ts = msg.created_at
            messages.append(msg)

        if not messages:
            return []

        return [
            ParsedConversation(
                conversation_id=f"claude-code-{path.stem}",
                title=path.stem,
                create_time=first_ts,
                messages=messages,
                metadata={"source_file": path.name, "source": "claude-code"},
            )
        ]

    def _extract_text(self, entry: dict) -> str:
        message = entry.get("message", {})
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, list):
                return "\n".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            return str(content)
        return str(message) if message else ""

    def parse_directory(self, directory: Path) -> list[ParsedConversation]:
        conversations: list[ParsedConversation] = []
        for ext in ("*.jsonl", "*.json"):
            for entry in sorted(directory.glob(ext)):
                conversations.extend(self.parse(entry))
        return conversations


class ClaudeExportParser(BaseParser):
    """Parse claude.ai JSON exports.

    The export format is a list of conversation objects, each with:
    - uuid, name, created_at
    - chat_messages: list of {sender, text, created_at}

    Usage::

        parser = ClaudeExportParser()
        convs = parser.parse(Path("conversations.json"))
    """

    def parse(self, path: Path) -> list[ParsedConversation]:
        with open(path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)

        entries: list[Any] = []
        if isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict):
            raw_entries = payload.get("conversations", payload.get("chats", []))
            if isinstance(raw_entries, list):
                entries = raw_entries

        conversations: list[ParsedConversation] = []
        for raw in entries:
            conv = self._parse_conversation(raw, path.name)
            if conv is not None:
                conversations.append(conv)

        return conversations

    def _parse_conversation(
        self, raw: dict, source_file: str
    ) -> ParsedConversation | None:
        chat_messages = raw.get("chat_messages", raw.get("messages", []))
        if not chat_messages:
            return None

        messages: list[ParsedMessage] = []
        for msg in chat_messages:
            sender = msg.get("sender", msg.get("role", ""))
            text = msg.get("text", msg.get("content", ""))
            if isinstance(text, list):
                text = "\n".join(
                    block.get("text", "")
                    for block in text
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            text = str(text).strip()
            if not text:
                continue

            role = self._map_role(sender)
            messages.append(
                ParsedMessage(
                    role=role,
                    content=text,
                    created_at=msg.get("created_at"),
                    message_id=msg.get("uuid"),
                )
            )

        if not messages:
            return None

        conv_id = raw.get("uuid", raw.get("id", f"claude-export-{id(raw)}"))
        return ParsedConversation(
            conversation_id=str(conv_id),
            title=raw.get("name", raw.get("title")),
            create_time=raw.get("created_at"),
            messages=messages,
            metadata={"source_file": source_file, "source": "claude-export"},
        )

    @staticmethod
    def _map_role(sender: str) -> str:
        sender_lower = sender.lower()
        if sender_lower in ("human", "user"):
            return "user"
        return "assistant"
