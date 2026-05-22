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

_DEFAULT_SOURCES = [Path("data/openai/export"), Path("data/gemini"), Path("data/claude")]


def _build_vector_index(conv_dir: Path, config: MemoryConfig) -> None:
    """Build vector embeddings index for all .md files."""
    from ..conversations.embeddings import SpacyEncoder
    from ..conversations.vector_store import VectorStore

    typer.echo(f"[vector] Carregando spaCy ({config.spacy_model})...")
    encoder = SpacyEncoder(model_name=config.spacy_model)

    vec_path = Path(config.vector_db_path)
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    store = VectorStore(vec_path, dim=config.embedding_dim)

    files = sorted(conv_dir.rglob("*.md"))
    if not files:
        typer.echo("[vector] Nenhum arquivo .md encontrado.")
        store.close()
        return

    count = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        if not text.strip():
            continue
        vec = encoder.encode(text)
        rel_path = str(f.relative_to(conv_dir))
        store.add(rel_path, vec, meta={"title": f.stem})
        count += 1

    store.close()
    typer.echo(f"[vector] Índice criado: {count} arquivos em {vec_path}")


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
    type: str = typer.Option("", "--type", "-t", help="Force parser: openai, gemini, claude-code, claude-export (auto-detect if empty)"),
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
    backend: str = typer.Option("ripgrep", "--backend", "-b", help="Backend: ripgrep, bm25, fts5, hybrid"),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Number of results"),
    expand: bool = typer.Option(False, "--expand", "-e", help="Expand query with semantically similar tokens"),
    conversations: Path = Path(""),
) -> None:
    """Search conversations without model inference."""

    from ..conversations.search import search as rg_search
    from ..conversations.search_bm25 import search_bm25
    from ..conversations.search_fts import search_fts
    from ..conversations.search_hybrid import search_hybrid
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

    import time
    t0 = time.perf_counter()

    if backend == "hybrid":
        from ..conversations.embeddings import SpacyEncoder
        from ..conversations.vector_store import VectorStore

        encoder = SpacyEncoder(model_name=config.spacy_model)
        vec_store = VectorStore(Path(config.vector_db_path), dim=config.embedding_dim)
        paths = search_hybrid(
            effective_query, conv_dir, encoder, vec_store,
            top_k=top_k, rrf_k=config.rrf_k,
        )
        vec_store.close()
    else:
        search_fn = backends.get(backend)
        if not search_fn:
            typer.echo(f"Unknown backend: {backend} (use: ripgrep, bm25, fts5, hybrid)", err=True)
            raise typer.Exit(code=1)
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
    backend: str = typer.Option("", "--backend", "-b", help="Backend to index: bm25, fts5, vector (empty = all)"),
    conversations: Path = Path(""),
) -> None:
    """Build search indexes for BM25, FTS5, and/or vector backends."""

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    backends = [backend] if backend else ["bm25", "fts5", "vector"]

    for b in backends:
        if b == "bm25":
            build_bm25_index(conv_dir)
        elif b == "fts5":
            build_fts_index(conv_dir)
        elif b == "vector":
            _build_vector_index(conv_dir, config)
        else:
            typer.echo(f"Unknown backend: {b} (use: bm25, fts5, vector)", err=True)


@app.command()
def migrate(
    conversations: Path = Path(""),
) -> None:
    """Migrate existing .md conversations into the structured memories database."""

    from ..db.migrate import migrate_v1_to_v2

    config = MemoryConfig()
    conv_dir = conversations if str(conversations) not in ("", ".") else Path(config.conversations_dir)
    db_path = Path(config.db_path)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Migrating conversations from {conv_dir}...")
    result = migrate_v1_to_v2(conv_dir, db_path)
    typer.echo(f"  Total: {result['total']} | Migrated: {result['migrated']} | Skipped: {result['skipped']}")


@app.command()
def stats() -> None:
    """Show overview of the memories database."""

    from ..db.store import stats as db_stats

    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found. Run 'mymem0ry migrate' first.")
        raise typer.Exit(code=1)

    result = db_stats(db_path)
    typer.echo(f"Total memories: {result['total']}\n")

    if result["by_scope"]:
        typer.echo("By scope:")
        for item in result["by_scope"]:
            typer.echo(f"  {item['scope']}: {item['count']}")

    if result["by_source"]:
        typer.echo("\nBy source:")
        for item in result["by_source"]:
            typer.echo(f"  {item['source']}: {item['count']}")

    if result["projects"]:
        typer.echo(f"\nProjects ({len(result['projects'])}):")
        for proj in result["projects"][:10]:
            typer.echo(f"  {proj['path']}: {proj['count']}")


@app.command()
def doctor() -> None:
    """Check system health: dependencies, indexes, database, permissions."""

    config = MemoryConfig()
    errors = 0
    warnings = 0

    def ok(msg: str) -> None:
        typer.echo(f"  [ok] {msg}")

    def warn(msg: str) -> None:
        nonlocal warnings
        warnings += 1
        typer.echo(f"  [warn] {msg}")

    def fail(msg: str) -> None:
        nonlocal errors
        errors += 1
        typer.echo(f"  [fail] {msg}")

    typer.echo("myMem0ry doctor\n")

    typer.echo("[1/6] spaCy model")
    try:
        import spacy
        nlp = spacy.util.get_installed_models()
        if config.spacy_model in nlp:
            ok(f"{config.spacy_model} instalado")
        else:
            fail(f"{config.spacy_model} nao encontrado (instale com: uv run spacy download {config.spacy_model})")
    except ImportError:
        fail("spacy nao instalado")

    typer.echo("[2/6] sqlite-vec")
    try:
        import sqlite_vec
        ok(f"sqlite-vec {sqlite_vec.sqlite_vec_version()}")
    except ImportError:
        fail("sqlite-vec nao instalado")

    typer.echo("[3/6] Database")
    db_path = Path(config.db_path)
    if db_path.exists():
        try:
            from ..db.schema import init_schema
            from ..db.connection import get_connection
            conn = get_connection(db_path)
            init_schema(conn)
            row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
            conn.close()
            ok(f"schema v{row['value']} em {db_path}")
        except Exception as e:
            fail(f"erro ao abrir DB: {e}")
    else:
        warn(f"DB nao encontrado em {db_path} (corra mymem0ry migrate)")

    typer.echo("[4/6] Indice BM25")
    conv_dir = Path(config.conversations_dir)
    bm25_path = conv_dir / ".bm25_index.pkl"
    if bm25_path.exists():
        ok(f"{bm25_path}")
    else:
        warn("indice BM25 nao encontrado (corra mymem0ry index --backend bm25)")

    typer.echo("[5/6] Indice FTS5")
    fts_path = conv_dir / ".fts5_index.db"
    if fts_path.exists():
        ok(f"{fts_path}")
    else:
        warn("indice FTS5 nao encontrado (corra mymem0ry index --backend fts5)")

    typer.echo("[6/6] Indice vector")
    vec_path = Path(config.vector_db_path)
    if vec_path.exists():
        ok(f"{vec_path}")
    else:
        warn("indice vector nao encontrado (corra mymem0ry index --backend vector)")

    typer.echo("")
    if errors:
        typer.echo(f"Resultado: {errors} erro(s), {warnings} aviso(s)")
        raise typer.Exit(code=1)
    elif warnings:
        typer.echo(f"Resultado: OK com {warnings} aviso(s)")
    else:
        typer.echo("Resultado: tudo OK")


@app.command()
def projects() -> None:
    """List projects with indexed memories."""

    from ..db.store import list_projects

    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found. Run 'mymem0ry migrate' first.")
        raise typer.Exit(code=1)

    result = list_projects(db_path)
    if not result:
        typer.echo("No projects found.")
        return

    typer.echo(f"{'Project path':<60} {'Memories':>8}")
    typer.echo("-" * 70)
    for proj in result:
        typer.echo(f"{proj['path']:<60} {proj['count']:>8}")
