"""Typer CLI for myMem0ry — personal memory search system."""

from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ..conversations.benchmark import format_table, run_benchmark
from ..conversations.search_bm25 import build_bm25_index
from ..conversations.search_fts import build_fts_index
from ..conversations.writer import split_conversations
from ..pipeline.dataset import build_dataset_from_openai

from ..conversations.spacy_expand import SpacyConceptSearch

app = typer.Typer(help="myMem0ry — personal memory search system")

_DEFAULT_SOURCES = [Path("data/openai/export"), Path("data/gemini")]


def _get_expander(config: MemoryConfig) -> SpacyConceptSearch:
    """Instantiate the spaCy concept search backend."""
    from ..conversations.spacy_expand import SpacyConceptSearch

    typer.echo(f"[expand] Carregando spaCy ({config.spacy_model})...")
    return SpacyConceptSearch(model_name=config.spacy_model)


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
    source: Path = Path(""),
    output: Path = Path("data/conversations"),
    type: str = typer.Option("", "--type", "-t", help="Force parser: openai, gemini (auto-detect if empty)"),
) -> None:
    """Split conversations into individual .md files organized by date."""

    explicit = str(source) not in ("", ".")
    sources = [source] if explicit else [s for s in _DEFAULT_SOURCES if s.exists()]

    if not sources:
        typer.echo("No source directories found.", err=True)
        raise typer.Exit(code=1)

    total_written = 0
    total_skipped = 0

    for src in sources:
        source_type = type if type else None
        typer.echo(f"Splitting conversations from {src}...")
        try:
            stats = split_conversations(src, output, source_type=source_type)
        except ValueError as e:
            typer.echo(f"  Skipping {src}: {e}", err=True)
            continue

        typer.echo(f"  {stats['written']} files written, {stats['skipped']} skipped")
        total_written += stats["written"]
        total_skipped += stats["skipped"]

    typer.echo(f"\nTotal: {total_written} files written, {total_skipped} skipped")


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
    from ..conversations.spacy_expand import expand_query_spacy

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    effective_query = query
    if expand:
        cs = _get_expander(config)
        effective_query = expand_query_spacy(query, cs, top_k=config.expand_top_k)
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

    from ..conversations.spacy_expand import expand_query_spacy

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    effective_query = question
    if expand:
        cs = _get_expander(config)
        effective_query = expand_query_spacy(question, cs, top_k=config.expand_top_k)
        typer.echo(f"[expand] Query expandida: {effective_query}\n")

    typer.echo(f"Query: {effective_query}\n")
    results = run_benchmark(effective_query, conv_dir, top_k=top_k)
    typer.echo(format_table(results))


@app.command()
def expand(
    query: str = typer.Argument(..., help="Query to expand"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of similar tokens"),
) -> None:
    """Show semantically related tokens for a query."""

    config = MemoryConfig()
    cs = _get_expander(config)

    results = cs.similar_tokens(query, top_k=top_k)
    if not results:
        typer.echo("Nenhum token similar encontrado.")
        return

    max_score = max(abs(s) for _, s in results) if results else 1.0
    score_width = 8 if max_score < 10 else 10

    typer.echo(f"Query: {query}\n")
    typer.echo(f"{'Token':<30} {'Score':>{score_width}}")
    typer.echo("-" * (30 + score_width + 1))
    for token, score in results:
        typer.echo(f"{token:<30} {score:>{score_width}.4f}")


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
