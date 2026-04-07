"""Convert parsed conversations into ChatML examples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..parsers.base import ParsedConversation, ParsedMessage


@dataclass
class ChatMLExample:
    """Minimal ChatML example stored as JSONL."""

    conversation_id: str
    chunk_index: int
    title: str | None
    messages: list[dict[str, str]]
    metadata: dict[str, str]


def build_chatml_examples(
    conversations: Sequence[ParsedConversation],
    *,
    max_seq_length: int = 2048,
    overlap_turns: int = 2,
    min_turns: int = 2,
    system_prompt: str | None = None,
) -> list[ChatMLExample]:
    """Return ChatML-formatted chunks that respect token limits."""

    max_chars = max(max_seq_length * 3, 1024)
    examples: list[ChatMLExample] = []
    for conversation in conversations:
        if not conversation.messages:
            continue
        chunks = _split_messages(
            conversation.messages, max_chars, overlap_turns, min_turns
        )
        for chunk_index, chunk in enumerate(chunks):
            messages = _build_messages(chunk, system_prompt)
            if len(messages) < min_turns:
                continue
            metadata = {
                "conversation_id": conversation.conversation_id,
                "title": conversation.title or "",
                "chunk_index": str(chunk_index),
                **conversation.metadata,
            }
            examples.append(
                ChatMLExample(
                    conversation_id=conversation.conversation_id,
                    chunk_index=chunk_index,
                    title=conversation.title,
                    messages=[
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in messages
                    ],
                    metadata=metadata,
                )
            )
    return examples


def _build_messages(
    chunk: Sequence[ParsedMessage], system_prompt: str | None
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if system_prompt:
        result.append({"role": "system", "content": system_prompt})
    for message in chunk:
        result.append({"role": message.role, "content": message.content})
    return result


def _split_messages(
    messages: Sequence[ParsedMessage],
    max_chars: int,
    overlap_turns: int,
    min_turns: int,
) -> list[list[ParsedMessage]]:
    chunks: list[list[ParsedMessage]] = []
    current: list[ParsedMessage] = []
    current_chars = 0
    for message in messages:
        message_chars = len(message.content)
        if (
            current
            and current_chars + message_chars > max_chars
            and len(current) >= min_turns
        ):
            chunks.append(current.copy())
            current = current[-overlap_turns:] if overlap_turns else []
            current_chars = sum(len(msg.content) for msg in current)
        current.append(message)
        current_chars += message_chars
    if len(current) >= min_turns:
        chunks.append(current)
    return chunks
