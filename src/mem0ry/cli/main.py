"""Typer CLI for the myMem0ry KV cache pipeline."""

from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ..kvcache.extract import extract_memories
from ..kvcache.model import build_cache, chat, load_model
from ..parsers.openai import OpenAIParser
from ..pipeline.dataset import build_dataset_from_openai

app = typer.Typer(help="myMem0ry — KV Cache personal memory system")


@app.command()
def build(
    source: Path = Path("data/openai/export"),
    output: Path = Path("data/memories"),
) -> None:
    """Parse conversations and extract memories via Ollama."""

    config = MemoryConfig()
    parser = OpenAIParser()

    typer.echo(f"Parsing OpenAI exports in {source}...")
    conversations = parser.parse_directory(source)
    typer.echo(f"Parsed {len(conversations)} conversations")

    if not conversations:
        typer.echo("No conversations found.", err=True)
        raise typer.Exit(code=1)

    typer.echo("Extracting memories...")
    memories_text = extract_memories(conversations, config=config)

    output.mkdir(parents=True, exist_ok=True)
    memories_path = output / "memories.txt"
    memories_path.write_text(memories_text, encoding="utf-8")
    typer.echo(f"Memories saved to {memories_path}")


@app.command(name="build-cache")
def build_cache_cmd(
    memories: Path = Path("data/memories/memories.txt"),
    model_name: str = "",
    max_tokens: int = 0,
) -> None:
    """Build KV cache from extracted memories (runs once)."""

    if not memories.exists():
        typer.echo(f"Memories file not found: {memories}", err=True)
        typer.echo("Run 'mymem0ry build' first.", err=True)
        raise typer.Exit(code=1)

    config = MemoryConfig()
    if model_name:
        config.kvcache_model = model_name
    if max_tokens > 0:
        config.kvcache_max_tokens = max_tokens

    memories_text = memories.read_text(encoding="utf-8")
    if not memories_text.strip():
        typer.echo("Memories file is empty.", err=True)
        raise typer.Exit(code=1)

    model_obj, tokenizer, _, _ = load_model(config)
    n_tokens = build_cache(
        memories_text, config=config, model=model_obj, tokenizer=tokenizer
    )
    typer.echo(f"KV cache built with {n_tokens} tokens")


@app.command(name="chat")
def chat_cmd(
    question: str = typer.Argument(..., help="Question to ask"),
    model_name: str = "",
) -> None:
    """Ask a question using the KV cache."""

    config = MemoryConfig()
    if model_name:
        config.kvcache_model = model_name

    model_obj, tokenizer, _, _ = load_model(config)
    answer = chat(question, config=config, model=model_obj, tokenizer=tokenizer)
    typer.echo(f"\n{answer}")


@app.command()
def interactive(
    model_name: str = "",
) -> None:
    """Interactive chat mode using KV cache."""

    config = MemoryConfig()
    if model_name:
        config.kvcache_model = model_name

    model_obj, tokenizer, _, _ = load_model(config)

    typer.echo("[memoria] Modo interativo. Digite 'sair' para encerrar.\n")
    while True:
        try:
            q = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("sair", "exit", "quit"):
            break
        if not q:
            continue
        answer = chat(q, config=config, model=model_obj, tokenizer=tokenizer)
        typer.echo(f"Modelo: {answer}\n")


@app.command()
def dataset(
    source: Path = Path("data/openai/export"),
    output: Path = Path("data/processed"),
    max_seq_length: int = 2048,
    val_ratio: float = 0.05,
    overlap_turns: int = 2,
    min_turns: int = 2,
) -> None:
    """Build ChatML JSONL dataset from OpenAI exports (legacy)."""

    import json

    config = MemoryConfig()
    result = build_dataset_from_openai(
        source=source,
        output=output,
        max_seq_length=max_seq_length,
        overlap_turns=overlap_turns,
        min_turns=min_turns,
        val_ratio=val_ratio,
        config=config,
    )
    typer.echo("Dataset built")
    typer.echo(json.dumps(result["stats"], indent=2))
