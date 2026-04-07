"""Deduplication helpers for ChatML examples."""

from __future__ import annotations

from hashlib import sha256
from typing import Sequence


def deduplicate_examples(examples: Sequence[dict]) -> list[dict]:
    """Return examples with duplicate content removed."""
    seen: set[str] = set()
    result: list[dict] = []
    for example in examples:
        payload = "".join(msg.get("content", "") for msg in example.get("messages", []))
        digest = sha256(payload.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        metadata = dict(example.get("metadata", {}))
        metadata["content_hash"] = digest
        example["metadata"] = metadata
        result.append(example)
    return result
