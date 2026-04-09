"""High-level dataset pipeline wiring OpenAI exports to ChatML JSONL."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from ..dataset import (
    apply_quality_filters,
    build_chatml_examples,
    compute_stats,
    deduplicate_examples,
    train_val_split,
)
from ..dataset.qa_cache import QACache, load_cache, make_entry, save_cache
from ..dataset.qa_generator import (
    QAPair,
    create_client,
    create_llamacpp_model,
    generate_qa_pairs,
    qa_pairs_to_chatml,
)
from ..dataset.temporal import build_temporal_system_prompt, enrich_conversations
from ..parsers.openai import OpenAIParser
from ..training.config import TrainingConfig
from ..utils.logging import configure_logging
from ..utils.paths import ensure_dir

LOGGER = configure_logging()


def _qa_description(conv_title: str | None, max_len: int = 40) -> str:
    if not conv_title:
        return "Generating QA..."
    return conv_title[:max_len] + ("..." if len(conv_title) > max_len else "")


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
    config: TrainingConfig | None = None,
    force_qa: bool = False,
    regen_qa_ids: Sequence[str] | None = None,
) -> dict[str, int | dict[str, int | float]]:
    """Build a ChatML dataset collection from OpenAI export files."""

    config = config or TrainingConfig()
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
            use_temporal=config.use_temporal,
        )
    ]
    LOGGER.info("Built %d ChatML chunks", len(raw_examples))

    qa_examples: list[dict] = []
    if config.enable_qa_generation:
        qa_examples = _generate_qa_incremental(
            conversations,
            config=config,
            base_prompt=base_prompt,
            force_qa=force_qa,
            regen_qa_ids=list(regen_qa_ids) if regen_qa_ids else None,
        )

    all_examples = raw_examples + qa_examples
    LOGGER.info(
        "Total examples: %d (chunks=%d, qa=%d)",
        len(all_examples),
        len(raw_examples),
        len(qa_examples),
    )

    filtered = apply_quality_filters(all_examples, min_turns=min_turns)
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
    stats_dict["processed_at"] = datetime.utcnow().isoformat()
    stats_dict["chunk_examples"] = len(raw_examples)
    stats_dict["qa_examples"] = len(qa_examples)
    _write_json(stats_dict, stats_path)

    return {
        "train": len(train),
        "val": len(val),
        "stats": stats_dict,
    }


def _generate_qa_incremental(
    conversations: Sequence,
    *,
    config: TrainingConfig,
    base_prompt: str,
    force_qa: bool = False,
    regen_qa_ids: list[str] | None = None,
) -> list[dict]:
    cache_path = Path(config.qa_cache_path).expanduser()
    cache = load_cache(cache_path)

    if force_qa:
        LOGGER.info("Force QA: clearing entire cache")
        cache = QACache()
    elif regen_qa_ids:
        for cid in regen_qa_ids:
            cache.remove(cid)
        LOGGER.info("Regenerating QA for %d conversation IDs", len(regen_qa_ids))

    client = None
    llama_model = None

    if config.qa_backend == "llamacpp":
        LOGGER.info("Loading llama.cpp model from %s", config.llamacpp_model_path)
        llama_model = create_llamacpp_model(
            config.llamacpp_model_path,
            n_gpu_layers=config.llamacpp_n_gpu_layers,
            n_ctx=config.llamacpp_n_ctx,
        )
        effective_model = config.llamacpp_model_path
    elif config.qa_backend == "ollama":
        client = create_client(
            "ollama",
            ollama_base_url=config.ollama_base_url,
        )
        effective_model = config.ollama_model
    else:
        client = create_client(
            "api",
            api_key=config.zai_api_key,
            base_url=config.zai_base_url,
        )
        effective_model = config.qa_generation_model

    backend: str = config.qa_backend
    all_qa_examples: list[dict] = []
    api_calls = 0

    eligible = [c for c in conversations if c.messages]
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
        task = progress.add_task("QA generation", total=len(eligible))

        for conv in eligible:
            progress.update(task, description=_qa_description(conv.title))

            content_hash = QACache.compute_hash(conv.messages)

            if not force_qa and not (
                regen_qa_ids and conv.conversation_id in regen_qa_ids
            ):
                if cache.is_cached(conv.conversation_id, content_hash):
                    cached = cache.get(conv.conversation_id)
                    qa_dicts = cached.qa_pairs if cached else []
                else:
                    qa_dicts = _call_api_and_cache(
                        conv,
                        client=client,
                        llama_model=llama_model,
                        model=effective_model,
                        n_pairs=config.qa_pairs_per_conversation,
                        cache=cache,
                        content_hash=content_hash,
                        backend=backend,
                    )
                    api_calls += 1
            else:
                qa_dicts = _call_api_and_cache(
                    conv,
                    client=client,
                    llama_model=llama_model,
                    model=effective_model,
                    n_pairs=config.qa_pairs_per_conversation,
                    cache=cache,
                    content_hash=content_hash,
                    backend=backend,
                )
                api_calls += 1

            qa_pairs = [
                QAPair(question=d["question"], answer=d["answer"]) for d in qa_dicts
            ]
            if qa_pairs:
                prompt = build_temporal_system_prompt(conv, base_prompt)
                conv_meta = {
                    "source_file": conv.metadata.get("source_file", ""),
                }
                examples = qa_pairs_to_chatml(
                    qa_pairs,
                    conversation_id=conv.conversation_id,
                    system_prompt=prompt,
                    metadata=conv_meta,
                )
                all_qa_examples.extend(examples)

            save_cache(cache, cache_path)
            progress.advance(task)

    LOGGER.info(
        "QA generation complete: %d pairs from %d API calls (cache has %d entries)",
        len(all_qa_examples),
        api_calls,
        len(cache.entries),
    )

    return all_qa_examples


def _call_api_and_cache(
    conv,
    *,
    client=None,
    llama_model=None,
    model: str,
    n_pairs: int,
    cache: QACache,
    content_hash: str,
    backend: str = "api",
) -> list[dict[str, str]]:
    try:
        pairs = generate_qa_pairs(
            conv,
            client=client,
            llama_model=llama_model,
            model=model,
            n_pairs=n_pairs,
            backend=backend,
        )
    except Exception as exc:
        LOGGER.warning(
            "QA generation failed for conversation %s: %s",
            conv.conversation_id,
            exc,
        )
        return []

    qa_dicts = [{"question": p.question, "answer": p.answer} for p in pairs]
    entry = make_entry(
        conversation_id=conv.conversation_id,
        content_hash=content_hash,
        qa_pairs=qa_dicts,
        model=model,
    )
    cache.add(entry)
    LOGGER.debug(
        "Generated %d QA pairs for conversation %s",
        len(qa_dicts),
        conv.conversation_id,
    )
    return qa_dicts


def _write_jsonl(examples: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        for example in examples:
            json.dump(example, stream, ensure_ascii=False)
            stream.write("\n")


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
