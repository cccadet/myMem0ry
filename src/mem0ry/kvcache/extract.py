"""Extract memories from conversations using Ollama API."""

from __future__ import annotations

from typing import Sequence

from openai import OpenAI

from ..config import MemoryConfig
from ..parsers.base import ParsedConversation
from ..utils.logging import configure_logging

LOGGER = configure_logging()

_EXTRACTION_SYSTEM_PROMPT = (
    "You are a memory extraction assistant. Your job is to read a conversation "
    "and extract factual memories about the user. Extract:\n"
    "- Personal info (name, age, location)\n"
    "- Preferences (food, music, hobbies, tools)\n"
    "- Projects and work details\n"
    "- Relationships (family, friends, pets)\n"
    "- Important events and dates\n"
    "- Opinions and beliefs\n\n"
    "Output each memory as a concise bullet point. Be specific — include names, "
    "numbers, and concrete details. Do not invent information. "
    "Write in third person about the user. Output plain text, one memory per line."
)

_EXTRACTION_USER_TEMPLATE = """\
Extract all factual memories about the user from this conversation:

---
{conversation_text}
---

List each memory as a concise bullet point:"""


def create_ollama_client(config: MemoryConfig | None = None) -> OpenAI:
    config = config or MemoryConfig()
    return OpenAI(
        api_key="ollama",
        base_url=config.ollama_base_url,
    )


def extract_memories_from_conversation(
    conversation: ParsedConversation,
    *,
    client: OpenAI,
    model: str,
    max_tokens: int = 2048,
    temperature: float = 0.3,
) -> str:
    lines = []
    for msg in conversation.messages:
        lines.append(f"[{msg.role}]: {msg.content}")
    conversation_text = "\n".join(lines)

    prompt = _EXTRACTION_USER_TEMPLATE.format(conversation_text=conversation_text)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def extract_memories(
    conversations: Sequence[ParsedConversation],
    config: MemoryConfig | None = None,
) -> str:
    config = config or MemoryConfig()
    client = create_ollama_client(config)
    model = config.ollama_model

    all_memories: list[str] = []
    total = len(conversations)

    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        MofNCompleteColumn,
        TimeElapsedColumn,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("Extracting memories", total=total)

        for i, conv in enumerate(conversations):
            title = conv.title or f"Conversation {i + 1}"
            desc = title[:40] + ("..." if len(title) > 40 else "")
            progress.update(task, description=desc)

            if not conv.messages:
                progress.advance(task)
                continue

            try:
                memories = extract_memories_from_conversation(
                    conv,
                    client=client,
                    model=model,
                    max_tokens=config.extraction_max_tokens,
                    temperature=config.extraction_temperature,
                )
                if memories.strip():
                    header = f"# {title}"
                    all_memories.append(f"{header}\n{memories.strip()}")
            except Exception as exc:
                LOGGER.warning(
                    "Memory extraction failed for %s: %s",
                    conv.conversation_id,
                    exc,
                )

            progress.advance(task)

    LOGGER.info("Extracted memories from %d conversations", len(all_memories))
    return "\n\n".join(all_memories)
