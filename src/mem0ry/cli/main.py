"""Typer CLI for myMem0ry — personal memory search system."""

from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ..conversations.benchmark import format_table, run_benchmark
from ..conversations.search_bm25 import build_bm25_index
from ..conversations.search_fts import build_fts_index
from ..conversations.writer import split_conversations
from ..parsers.openai import OpenAIParser
from ..pipeline.dataset import build_dataset_from_openai

app = typer.Typer(help="myMem0ry — personal memory search system")


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


@app.command()
def split(
    source: Path = Path("data/openai/export"),
    output: Path = Path("data/conversations"),
) -> None:
    """Split conversations into individual .md files organized by date."""

    if not source.exists():
        typer.echo(f"Source directory not found: {source}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Splitting conversations from {source}...")
    stats = split_conversations(source, output)

    typer.echo(f"Done: {stats['written']} files written, {stats['skipped']} skipped")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    backend: str = typer.Option("ripgrep", "--backend", "-b", help="Backend: ripgrep, bm25, fts5"),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Number of results"),
    expand: bool = typer.Option(False, "--expand", "-e", help="Expand query with semantically similar tokens"),
    conversations: Path = Path(""),
) -> None:
    """Search conversations without model inference."""

    from ..conversations.search import search as rg_search
    from ..conversations.search_bm25 import search_bm25
    from ..conversations.search_fts import search_fts

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    # Optionally expand query with semantically similar tokens
    effective_query = query
    if expand:
        from ..conversations.query_expansion import ConceptSearch, expand_query

        typer.echo(f"[expand] Carregando modelo {config.model_name}...")
        cs = ConceptSearch(model_name=config.model_name)
        effective_query = expand_query(query, cs, top_k=config.expand_top_k)
        typer.echo(f"[expand] Query expandida: {effective_query}")

    backends = {"ripgrep": rg_search, "bm25": search_bm25, "fts5": search_fts}
    search_fn = backends.get(backend)
    if not search_fn:
        typer.echo(f"Unknown backend: {backend} (use: ripgrep, bm25, fts5)", err=True)
        raise typer.Exit(code=1)

    import time
    t0 = time.perf_counter()
    paths = search_fn(effective_query, conv_dir, top_k=top_k)
    elapsed = (time.perf_counter() - t0) * 1000

    if not paths:
        typer.echo("Nenhum resultado encontrado.")
        return

    typer.echo(f"[{backend}] {len(paths)} resultados em {elapsed:.1f}ms\n")
    for p in paths:
        typer.echo(f"  {p.relative_to(conv_dir)}")


@app.command()
def benchmark(
    question: str = typer.Argument(..., help="Query to benchmark"),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Number of results per backend"),
    expand: bool = typer.Option(False, "--expand", "-e", help="Expand query with semantically similar tokens"),
    conversations: Path = Path(""),
) -> None:
    """Compare search backends side by side."""

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    # Optionally expand query
    effective_query = question
    if expand:
        from ..conversations.query_expansion import ConceptSearch, expand_query

        typer.echo(f"[expand] Carregando modelo {config.model_name}...")
        cs = ConceptSearch(model_name=config.model_name)
        effective_query = expand_query(question, cs, top_k=config.expand_top_k)
        typer.echo(f"[expand] Query expandida: {effective_query}\n")

    typer.echo(f"Query: {effective_query}\n")
    results = run_benchmark(effective_query, conv_dir, top_k=top_k)
    typer.echo(format_table(results))


@app.command()
def index(
    backend: str = typer.Option("", "--backend", "-b", help="Backend to index: bm25, fts5 (empty = all)"),
    conversations: Path = Path(""),
) -> None:
    """Build search indexes for BM25 and/or FTS5 backends."""

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    backends = [backend] if backend else ["bm25", "fts5"]

    for b in backends:
        if b == "bm25":
            build_bm25_index(conv_dir)
        elif b == "fts5":
            build_fts_index(conv_dir)
        else:
            typer.echo(f"Unknown backend: {b} (use: bm25, fts5)", err=True)
