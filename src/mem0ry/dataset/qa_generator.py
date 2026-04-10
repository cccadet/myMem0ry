"""Generate synthetic Q&A pairs from conversations using an LLM backend."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

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


QABackend = Literal["api", "ollama", "llamacpp", "turns"]


def create_client(
    backend: QABackend = "api",
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    ollama_base_url: str | None = None,
) -> OpenAI:
    if backend == "ollama":
        return OpenAI(
            api_key="ollama",
            base_url=ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
    return OpenAI(
        api_key=api_key or os.environ.get("ZAI_API_KEY", ""),
        base_url=base_url
        or os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/"),
    )


def create_llamacpp_model(
    model_path: str | None = None,
    *,
    n_gpu_layers: int = -1,
    n_ctx: int = 4096,
):
    from llama_cpp import Llama

    path = model_path or os.environ.get("LLAMACPP_MODEL_PATH", "")
    if not path:
        raise ValueError(
            "llamacpp backend requires a model path. "
            "Set --llamacpp-model or LLAMACPP_MODEL_PATH env var."
        )
    return Llama(
        model_path=path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
        verbose=False,
    )


_LOCAL_SYSTEM_PROMPT = (
    "You are a data annotation assistant. Read the conversation and generate "
    "question-answer pairs about it. Be specific and include dates when available. "
    "Reply with ONLY a JSON array like: "
    '[{"question": "...", "answer": "..."}]'
)


def _get_system_prompt(backend: QABackend) -> str:
    if backend in ("ollama", "llamacpp"):
        return _LOCAL_SYSTEM_PROMPT
    return _QA_SYSTEM_PROMPT


def generate_qa_pairs(
    conversation: ParsedConversation,
    *,
    client: OpenAI | None = None,
    llama_model=None,
    model: str | None = None,
    n_pairs: int = 4,
    backend: QABackend = "api",
) -> list[QAPair]:
    prompt = _build_prompt(conversation, n_pairs)
    system = _get_system_prompt(backend)

    if backend == "llamacpp":
        return _generate_qa_llamacpp(llama_model, system, prompt)

    model = model or os.environ.get("QA_GENERATION_MODEL", "glm-4.7-flashx")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    raw = response.choices[0].message.content or ""
    return _parse_response(raw)


def _generate_qa_llamacpp(
    llama_model,
    system: str,
    prompt: str,
) -> list[QAPair]:
    response = llama_model.create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    raw = response["choices"][0]["message"]["content"] or ""
    return _parse_response(raw)


def generate_qa_from_turns(
    conversation: ParsedConversation,
) -> list[QAPair]:
    pairs: list[QAPair] = []
    messages = conversation.messages
    for i in range(len(messages) - 1):
        if messages[i].role == "user" and messages[i + 1].role == "assistant":
            q = messages[i].content.strip()
            a = messages[i + 1].content.strip()
            if q and a:
                pairs.append(QAPair(question=q, answer=a))
    return pairs


def generate_qa_batch(
    conversations: Sequence[ParsedConversation],
    *,
    client: OpenAI | None = None,
    llama_model=None,
    model: str | None = None,
    n_pairs: int = 4,
    backend: QABackend = "api",
) -> dict[str, list[QAPair]]:
    results: dict[str, list[QAPair]] = {}
    for conv in conversations:
        if not conv.messages:
            continue
        try:
            pairs = generate_qa_pairs(
                conv,
                client=client,
                llama_model=llama_model,
                model=model,
                n_pairs=n_pairs,
                backend=backend,
            )
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
