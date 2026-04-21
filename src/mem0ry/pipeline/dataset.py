"""High-level dataset pipeline wiring OpenAI exports to ChatML JSONL."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..config import MemoryConfig
from ..dataset import (
    apply_quality_filters,
    build_chatml_examples,
    compute_stats,
    deduplicate_examples,
    train_val_split,
)
from ..dataset.temporal import enrich_conversations
from ..parsers.openai import OpenAIParser
from ..utils.logging import configure_logging
from ..utils.paths import ensure_dir

LOGGER = configure_logging()


def build_dataset_from_openai(
    *,
    source: Path,
    output: Path,
    system_prompt: str | None = None,
    max_seq_length: int = 2048,
    overlap_turns: int = 2,
    min_turns: int = 2,
    val_ratio: float = 0.05,
    seed: int = 42,
    config: MemoryConfig | None = None,
) -> dict[str, int | dict[str, int | float]]:
    config = config or MemoryConfig()
    source = source.expanduser()
    output = output.expanduser()

    base_prompt = system_prompt or config.system_prompt

    parser = OpenAIParser()
    LOGGER.info("Parsing OpenAI exports in %s", source)
    conversations = parser.parse_directory(source)
    LOGGER.info("Parsed %d conversations", len(conversations))

    conversations = enrich_conversations(conversations)
    LOGGER.info("Sorted %d conversations chronologically", len(conversations))

    raw_examples = [
        asdict(example)
        for example in build_chatml_examples(
            conversations,
            max_seq_length=max_seq_length,
            overlap_turns=overlap_turns,
            min_turns=min_turns,
            system_prompt=base_prompt,
            use_temporal=True,
        )
    ]
    LOGGER.info("Built %d ChatML chunks", len(raw_examples))

    filtered = apply_quality_filters(raw_examples, min_turns=min_turns)
    LOGGER.info("Retained %d examples after quality filtering", len(filtered))

    deduped = deduplicate_examples(filtered)
    LOGGER.info("Deduplicated down to %d examples", len(deduped))

    stats = compute_stats(deduped)

    train, val = train_val_split(deduped, val_ratio=val_ratio, seed=seed)
    LOGGER.info("Split into %d train / %d val", len(train), len(val))

    ensure_dir(output)
    train_path = output / "train.jsonl"
    val_path = output / "val.jsonl"
    stats_path = output / "stats.json"

    _write_jsonl(train, train_path)
    _write_jsonl(val, val_path)
    stats_dict = stats.to_dict()
    stats_dict["total_examples"] = len(train) + len(val)
    stats_dict["processed_at"] = datetime.now(timezone.utc).isoformat()
    stats_dict["chunk_examples"] = len(raw_examples)
    _write_json(stats_dict, stats_path)

    return {
        "train": len(train),
        "val": len(val),
        "stats": stats_dict,
    }


def _write_jsonl(examples: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        for example in examples:
            json.dump(example, stream, ensure_ascii=False)
            stream.write("\n")


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
