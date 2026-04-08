"""Generate synthetic Q&A pairs from conversations using the z.ai API."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from openai import OpenAI

from ..parsers.base import ParsedConversation
from .temporal import format_timestamp

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

_QA_SYSTEM_PROMPT = (
    "You are a data annotation assistant. Your job is to read a conversation "
    "and generate question-answer pairs that test detailed knowledge of what "
    "was discussed. Each answer must be specific, reference concrete details "
    "from the conversation, and include the date when available."
)

_QA_USER_TEMPLATE = """\
Given this conversation{date_clause}{title_clause}:

---
{conversation_text}
---

Generate exactly {n_pairs} question-answer pairs about this conversation.
Include a mix of:
- Factual questions ("What did the user say about X?")
- Temporal questions ("When did the user discuss X?" or "What was discussed on this date?")
- Preference/opinion questions ("What was the user's opinion on X?")

Respond with ONLY a JSON array, no other text. Format:
[{{"question": "...", "answer": "..."}}]
"""


@dataclass
class QAPair:
    question: str
    answer: str


def create_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> OpenAI:
    return OpenAI(
        api_key=api_key or os.environ.get("ZAI_API_KEY", ""),
        base_url=base_url
        or os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/"),
    )


def generate_qa_pairs(
    conversation: ParsedConversation,
    *,
    client: OpenAI,
    model: str | None = None,
    n_pairs: int = 4,
) -> list[QAPair]:
    model = model or os.environ.get("QA_GENERATION_MODEL", "glm-4.7-flashx")
    prompt = _build_prompt(conversation, n_pairs)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _QA_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2048,
    )

    raw = response.choices[0].message.content or ""
    return _parse_response(raw)


def generate_qa_batch(
    conversations: Sequence[ParsedConversation],
    *,
    client: OpenAI,
    model: str | None = None,
    n_pairs: int = 4,
) -> dict[str, list[QAPair]]:
    results: dict[str, list[QAPair]] = {}
    for conv in conversations:
        if not conv.messages:
            continue
        try:
            pairs = generate_qa_pairs(conv, client=client, model=model, n_pairs=n_pairs)
            results[conv.conversation_id] = pairs
        except Exception:
            results[conv.conversation_id] = []
    return results


def _build_prompt(conversation: ParsedConversation, n_pairs: int) -> str:
    date_str = format_timestamp(conversation.create_time)
    date_clause = f" from {date_str}" if date_str else ""
    title_clause = f' (titled "{conversation.title}")' if conversation.title else ""

    lines: list[str] = []
    for msg in conversation.messages:
        lines.append(f"[{msg.role}]: {msg.content}")
    conversation_text = "\n".join(lines)

    return _QA_USER_TEMPLATE.format(
        date_clause=date_clause,
        title_clause=title_clause,
        conversation_text=conversation_text,
        n_pairs=n_pairs,
    )


def _parse_response(text: str) -> list[QAPair]:
    json_match = re.search(r"\[.*\]", text, re.DOTALL)
    if not json_match:
        return []

    try:
        items = json.loads(json_match.group())
    except json.JSONDecodeError:
        return []

    pairs: list[QAPair] = []
    for item in items:
        q = item.get("question", "").strip()
        a = item.get("answer", "").strip()
        if q and a:
            pairs.append(QAPair(question=q, answer=a))
    return pairs


def qa_pairs_to_chatml(
    qa_pairs: Sequence[QAPair],
    *,
    conversation_id: str,
    system_prompt: str,
    chunk_index: int = 0,
    metadata: dict[str, str] | None = None,
) -> list[dict]:
    examples: list[dict] = []
    for i, pair in enumerate(qa_pairs):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pair.question},
            {"role": "assistant", "content": pair.answer},
        ]
        meta = {
            "conversation_id": conversation_id,
            "chunk_index": str(chunk_index),
            "qa_index": str(i),
            "source": "qa_generated",
            **(metadata or {}),
        }
        examples.append(
            {
                "conversation_id": conversation_id,
                "chunk_index": chunk_index,
                "title": None,
                "messages": messages,
                "metadata": meta,
            }
        )
    return examples
