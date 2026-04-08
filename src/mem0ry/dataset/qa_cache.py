"""Incremental Q&A cache backed by a JSONL file."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from ..parsers.base import ParsedMessage


@dataclass
class QACacheEntry:
    conversation_id: str
    content_hash: str
    qa_pairs: list[dict[str, str]]
    generated_at: str
    model: str


@dataclass
class QACache:
    entries: dict[str, QACacheEntry] = field(default_factory=dict)

    @staticmethod
    def compute_hash(messages: Sequence[ParsedMessage]) -> str:
        payload = "".join(msg.content for msg in messages)
        return sha256(payload.encode("utf-8")).hexdigest()

    def is_cached(self, conversation_id: str, content_hash: str) -> bool:
        entry = self.entries.get(conversation_id)
        return entry is not None and entry.content_hash == content_hash

    def get(self, conversation_id: str) -> QACacheEntry | None:
        return self.entries.get(conversation_id)

    def add(self, entry: QACacheEntry) -> None:
        self.entries[entry.conversation_id] = entry

    def remove(self, conversation_id: str) -> None:
        self.entries.pop(conversation_id, None)


def load_cache(path: Path) -> QACache:
    cache = QACache()
    if not path.exists():
        return cache
    with open(path, "r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entry = QACacheEntry(
                    conversation_id=data["conversation_id"],
                    content_hash=data["content_hash"],
                    qa_pairs=data["qa_pairs"],
                    generated_at=data["generated_at"],
                    model=data["model"],
                )
                cache.entries[entry.conversation_id] = entry
            except (json.JSONDecodeError, KeyError):
                continue
    return cache


def save_cache(cache: QACache, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        for entry in cache.entries.values():
            json.dump(asdict(entry), stream, ensure_ascii=False)
            stream.write("\n")


def make_entry(
    conversation_id: str,
    content_hash: str,
    qa_pairs: list[dict[str, str]],
    model: str,
) -> QACacheEntry:
    return QACacheEntry(
        conversation_id=conversation_id,
        content_hash=content_hash,
        qa_pairs=qa_pairs,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
        model=model,
    )
