"""Typer CLI for myMem0ry — personal memory search system."""

from __future__ import annotations

import os
from datetime import date
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any

import typer

from ..config import MemoryConfig
from ..conversations.benchmark import format_table, run_benchmark
from ..conversations.search_bm25 import build_bm25_index
from ..conversations.search_fts import build_fts_index
from ..conversations.writer import split_conversations
from ..pipeline.dataset import build_dataset_from_openai

from ..conversations.spacy_expand import SpacyConceptSearch

_HELP_WORKDIR = "Working directory"
_HELP_SESSION = "Session ID"

app = typer.Typer(help="myMem0ry — personal memory search system")


@app.command()
def version() -> None:
    """Show mymem0ry version."""
    try:
        typer.echo(f"mymem0ry {pkg_version('mymem0ry')}")
    except Exception:
        typer.echo("mymem0ry (unknown version)")


_DEFAULT_SOURCES = [
    Path("data/openai/export"),
    Path("data/gemini"),
    Path("data/claude"),
]


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
    type: str = typer.Option(
        "",
        "--type",
        "-t",
        help="Force parser: openai, gemini, claude-code, claude-export (auto-detect if empty)",
    ),
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
    backend: str = typer.Option(
        "ripgrep", "--backend", "-b", help="Backend: ripgrep, bm25, fts5, hybrid"
    ),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Number of results"),
    expand: bool = typer.Option(
        False, "--expand", "-e", help="Expand query with semantically similar tokens"
    ),
    conversations: Path = Path(""),
) -> None:
    """Search conversations without model inference."""

    from ..conversations.search import search as rg_search
    from ..conversations.search_bm25 import search_bm25
    from ..conversations.search_fts import search_fts
    from ..conversations.search_hybrid import search_hybrid
    from ..conversations.spacy_expand import expand_query_spacy

    config = MemoryConfig()
    conv_dir = (
        conversations
        if str(conversations) not in ("", ".")
        else Path(config.conversations_dir)
    )

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
            effective_query,
            conv_dir,
            encoder,
            vec_store,
            top_k=top_k,
            rrf_k=config.rrf_k,
        )
        vec_store.close()
    else:
        search_fn = backends.get(backend)
        if not search_fn:
            typer.echo(
                f"Unknown backend: {backend} (use: ripgrep, bm25, fts5, hybrid)",
                err=True,
            )
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
    expand: bool = typer.Option(
        False, "--expand", "-e", help="Expand query with semantically similar tokens"
    ),
    conversations: Path = Path(""),
) -> None:
    """Compare search backends side by side."""

    from ..conversations.spacy_expand import expand_query_spacy

    config = MemoryConfig()
    conv_dir = (
        conversations
        if str(conversations) not in ("", ".")
        else Path(config.conversations_dir)
    )

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
    backend: str = typer.Option(
        "", "--backend", "-b", help="Backend to index: bm25, fts5, vector (empty = all)"
    ),
    conversations: Path = Path(""),
) -> None:
    """Build search indexes for BM25, FTS5, and/or vector backends."""

    config = MemoryConfig()
    conv_dir = (
        conversations
        if str(conversations) not in ("", ".")
        else Path(config.conversations_dir)
    )

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
    reprocess: bool = typer.Option(
        False, "--reprocess", help="Drop DB and reingest all .md files into v3 schema"
    ),
) -> None:
    """Migrate existing .md conversations into the structured memories database."""

    config = MemoryConfig()
    conv_dir = (
        conversations
        if str(conversations) not in ("", ".")
        else Path(config.conversations_dir)
    )
    db_path = Path(config.db_path)

    if not conv_dir.exists():
        typer.echo(f"Conversations directory not found: {conv_dir}", err=True)
        raise typer.Exit(code=1)

    if reprocess:
        from ..db.migrate import migrate_v2_to_v3

        typer.echo(f"Reprocessing conversations from {conv_dir} (v3 schema)...")
        result = migrate_v2_to_v3(conv_dir, db_path)
    else:
        from ..db.migrate import migrate_v1_to_v2

        typer.echo(f"Migrating conversations from {conv_dir}...")
        result = migrate_v1_to_v2(conv_dir, db_path)

    typer.echo(
        f"  Total: {result['total']} | Migrated: {result['migrated']} | Skipped: {result['skipped']}"
    )


@app.command()
def stats() -> None:
    """Show overview of the memories database."""

    from ..db.store import stats as db_stats

    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo(
            "Database not found. Run 'mymem0ry migrate' or use the MCP server first."
        )
        raise typer.Exit(code=0)

    try:
        result = db_stats(db_path)
    except Exception as exc:
        typer.echo(f"Error reading database: {exc}")
        raise typer.Exit(code=1)
    typer.echo(f"Total memories: {result['total']}\n")

    if result["by_scope"]:
        typer.echo("By scope:")
        for item in result["by_scope"]:
            typer.echo(f"  {item['scope']}: {item['count']}")

    if result.get("by_type"):
        typer.echo("\nBy type:")
        for item in result["by_type"]:
            typer.echo(f"  {item['memory_type']}: {item['count']}")

    if result["by_source"]:
        typer.echo("\nBy source:")
        for item in result["by_source"]:
            typer.echo(f"  {item['source']}: {item['count']}")

    if result["projects"]:
        typer.echo(f"\nProjects ({len(result['projects'])}):")
        for proj in result["projects"][:10]:
            typer.echo(f"  {proj['project_id']}: {proj['count']}")


def _download_spacy_model(model: str) -> None:
    import shutil
    import subprocess
    import sys

    from spacy.cli.download import get_compatibility, get_version
    import spacy.about

    compat = get_compatibility()
    ver = get_version(model, compat)
    wheel_url = (
        f"{spacy.about.__download_url__}"
        f"/{model}-{ver}"
        f"/{model}-{ver}-py3-none-any.whl"
    )
    uv = shutil.which("uv")
    cmd = [uv, "pip", "install", "--python", sys.executable, wheel_url] if uv else [
        sys.executable, "-m", "pip", "install", wheel_url
    ]
    subprocess.check_call(cmd)


def _check_spacy(config: MemoryConfig, ok: Any, fail: Any) -> None:
    typer.echo("[1/6] spaCy model")
    try:
        import spacy

        nlp = spacy.util.get_installed_models()
        if config.spacy_model in nlp:
            ok(f"{config.spacy_model} instalado")
        else:
            pkg_name = config.spacy_model.replace("_", "-")
            typer.echo(f"  Baixando {pkg_name}...")
            _download_spacy_model(config.spacy_model)
            ok(f"{config.spacy_model} instalado")
    except ImportError:
        fail("spacy nao instalado")


def _check_db(config: MemoryConfig, ok: Any, warn: Any, fail: Any) -> None:
    typer.echo("[3/6] Database")
    db_path = Path(config.db_path)
    if not db_path.exists():
        warn(f"DB nao encontrado em {db_path} (corra mymem0ry migrate)")
        return
    try:
        from ..db.schema import init_schema
        from ..db.connection import get_connection

        conn = get_connection(db_path)
        init_schema(conn)
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        conn.close()
        ok(f"schema v{row['value']} em {db_path}")
    except Exception as e:
        fail(f"erro ao abrir DB: {e}")


def _check_index(label: str, path: Path, ok: Any, warn: Any, hint: str) -> None:
    typer.echo(label)
    if path.exists():
        ok(f"{path}")
    else:
        warn(f"indice {hint} nao encontrado (corra mymem0ry index --backend {hint})")


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

    _check_spacy(config, ok, fail)

    typer.echo("[2/6] sqlite-vec")
    try:
        import sqlite_vec

        ok(f"sqlite-vec {sqlite_vec.__version__}")
    except ImportError:
        fail("sqlite-vec nao instalado")

    _check_db(config, ok, warn, fail)

    conv_dir = Path(config.conversations_dir)
    _check_index("[4/6] Indice BM25", conv_dir / ".bm25_index.pkl", ok, warn, "bm25")
    _check_index("[5/6] Indice FTS5", conv_dir / ".fts5_index.db", ok, warn, "fts5")
    _check_index("[6/6] Indice vector", Path(config.vector_db_path), ok, warn, "vector")

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

    typer.echo(f"{'Project ID':<50} {'Path':<40} {'Memories':>8}")
    typer.echo("-" * 100)
    for proj in result:
        typer.echo(
            f"{proj['project_id'] or '-':<50} {proj['project_path'] or '-':<40} {proj['count']:>8}"
        )


@app.command()
def context(
    cwd: str = typer.Option(
        "", "--cwd", help="Working directory to resolve context from"
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of memories to load"),
    session: str = typer.Option("", "--session", "-s", help=_HELP_SESSION),
) -> None:
    """Load aggregated context for the current project. Prints to stdout for hooks."""

    from ..db.store import get_context
    from ..utils.git_context import resolve_full_context

    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        return

    work_dir = Path(cwd) if cwd else Path.cwd()
    resolved = resolve_full_context(work_dir, session or None)
    memories = get_context(
        db_path,
        project_id=resolved.get("project_id"),
        context=resolved.get("context"),
        session_id=resolved.get("session_id"),
        top_k=top_k,
    )

    if not memories:
        return

    for mem in memories:
        scope = mem.get("scope", "?")
        title = mem.get("title") or ""
        content = mem.get("content", "")
        line = f"[{scope}] {title}: {content}" if title else f"[{scope}] {content}"
        typer.echo(line)


@app.command()
def save(
    title: str = typer.Argument(..., help="Memory title"),
    content: str = typer.Argument("", help="Memory content (reads stdin if empty)"),
    cwd: str = typer.Option("", "--cwd", help=_HELP_WORKDIR),
    scope: str = typer.Option("session", "--scope", "-s", help="Memory scope"),
    memory_type: str = typer.Option("log", "--type", "-t", help="Memory type"),
    source: str = typer.Option("manual", "--source", help="Source agent"),
    session: str = typer.Option("", "--session", help=_HELP_SESSION),
) -> None:
    """Save a memory. Reads content from stdin if not provided as argument."""

    from ..db.store import create_memory
    from ..utils.git_context import resolve_full_context

    if not content:
        import sys

        if not sys.stdin.isatty():
            content = sys.stdin.read()
        if not content:
            typer.echo("No content provided.", err=True)
            raise typer.Exit(code=1)

    config = MemoryConfig()
    db_path = Path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = Path(cwd) if cwd else Path.cwd()
    resolved = resolve_full_context(work_dir, session or None)

    mem_id = create_memory(
        db_path,
        content=content,
        scope=scope,
        project_id=resolved.get("project_id"),
        project_path=resolved.get("project_path"),
        context=resolved.get("context"),
        session_id=resolved.get("session_id"),
        memory_type=memory_type,
        source=source,
        title=title,
    )
    typer.echo(mem_id)


@app.command()
def log(
    content: str = typer.Argument("", help="Log message (reads stdin if empty)"),
    cwd: str = typer.Option("", "--cwd", help=_HELP_WORKDIR),
    role: str = typer.Option("user", "--role", "-r", help="Role: user or assistant"),
    session: str = typer.Option("", "--session", help=_HELP_SESSION),
) -> None:
    """Quick-log a message to session memory. Reads from stdin if no argument."""

    import sys

    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        if not content:
            return

    config = MemoryConfig()
    db_path = Path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = Path(cwd) if cwd else Path.cwd()

    from ..utils.git_context import resolve_full_context

    resolved = resolve_full_context(work_dir, session or None)

    from ..db.store import create_memory

    create_memory(
        db_path,
        content=f"[{role}] {content}",
        scope="session",
        project_id=resolved.get("project_id"),
        project_path=resolved.get("project_path"),
        context=resolved.get("context"),
        session_id=resolved.get("session_id"),
        memory_type="log",
        source="manual",
        title=f"{role} message",
    )


@app.command()
def decay(
    days: int = typer.Option(90, "--days", "-d", help="Legacy — ignored, kept for compat"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without deleting"),
) -> None:
    """Remove old unpinned memories past their retention threshold (uses forget-sweep)."""

    from ..db.retention import forget_sweep

    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found. Run 'mymem0ry migrate' first.")
        raise typer.Exit(code=1)

    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    mode = "Would soft-delete" if dry_run else "Soft-deleted"
    soft_deleted = result.get("soft_deleted", [])
    soft_count = int(result.get("soft_count", 0))
    hard_count = int(result.get("hard_count", 0))
    typer.echo(
        f"{mode} {soft_count} memories, "
        f"hard-deleted {hard_count} expired"
    )
    if soft_deleted and dry_run:
        for m in soft_deleted[:20]:
            typer.echo(
                f"  {m['id']} ({m['memory_type']}/{m['tier']}, "
                f"salience={m['salience']:.3f}, {m['days_old']}d old)"
            )
        if len(soft_deleted) > 20:
            typer.echo(f"  ... and {len(soft_deleted) - 20} more")


@app.command()
def pin(memory_id: str = typer.Argument(..., help="Memory ID to pin")) -> None:
    """Pin a memory — exempt from retention decay."""

    from ..db.retention import pin_memory

    config = MemoryConfig()
    db_path = Path(config.db_path)
    found = pin_memory(db_path, memory_id)
    if found:
        typer.echo(f"Pinned {memory_id}")
    else:
        typer.echo(f"Memory {memory_id} not found or already deleted", err=True)
        raise typer.Exit(code=1)


@app.command()
def unpin(memory_id: str = typer.Argument(..., help="Memory ID to unpin")) -> None:
    """Unpin a memory — subject to retention decay again."""

    from ..db.retention import unpin_memory

    config = MemoryConfig()
    db_path = Path(config.db_path)
    found = unpin_memory(db_path, memory_id)
    if found:
        typer.echo(f"Unpinned {memory_id}")
    else:
        typer.echo(f"Memory {memory_id} not found", err=True)
        raise typer.Exit(code=1)


@app.command(name="forget-sweep")
def forget_sweep_cmd(
    dry_run: bool = typer.Option(
        True, "--execute/--dry-run", help="Execute sweep (default is dry-run preview)"
    ),
) -> None:
    """Sweep stale memories: soft-delete low-salience + hard-delete expired grace period."""

    from ..db.retention import forget_sweep

    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found.")
        raise typer.Exit(code=1)

    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    soft_deleted = result.get("soft_deleted", [])
    soft_count = int(result.get("soft_count", 0))
    hard_count = int(result.get("hard_count", 0))
    hard_deleted = result.get("hard_deleted", [])
    mode = "Preview" if dry_run else "Executed"
    typer.echo(f"\n{mode} forget-sweep:")
    typer.echo(f"  Soft-delete candidates: {soft_count}")
    typer.echo(f"  Hard-delete expired:    {hard_count}")

    if soft_deleted:
        typer.echo("\n  Soft-delete candidates:")
        for m in soft_deleted[:30]:
            typer.echo(
                f"    {m['id']}  {m['memory_type']:<8} tier={m['tier']:<11} "
                f"salience={m['salience']:.3f}  age={m['days_old']}d"
            )
        if len(soft_deleted) > 30:
            typer.echo(f"    ... and {len(soft_deleted) - 30} more")

    if hard_deleted:
        typer.echo(f"\n  Hard-deleted (grace expired): {hard_count}")

    if dry_run and (soft_count or hard_count):
        typer.echo("\n  Run with --execute to apply changes.")


@app.command()
def serve(
    host: str = typer.Option("", "--host", help="Bind address"),
    port: int = typer.Option(0, "--port", "-p", help="Bind port"),
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
) -> None:
    """Start the myMem0ry HTTP server (MCP + hook endpoint + handoffs)."""

    config = MemoryConfig()
    bind_host = host or config.server_host
    bind_port = port or config.server_port

    if detach:
        import subprocess
        import sys

        pid_file = Path(config.server_pid_file)
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        from ..daemon import is_server_running

        if is_server_running():
            typer.echo(f"Server already running at http://{bind_host}:{bind_port}")
            return

        cmd = [
            sys.executable,
            "-m",
            "mem0ry.mcp_server",
        ]
        env = {
            **os.environ,
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": bind_host,
            "MCP_PORT": str(bind_port),
        }
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        pid_file.write_text(str(proc.pid))
        typer.echo(f"Server started (pid {proc.pid}) at http://{bind_host}:{bind_port}")
        return

    os.environ["MCP_TRANSPORT"] = "streamable-http"
    os.environ["MCP_HOST"] = bind_host
    os.environ["MCP_PORT"] = str(bind_port)

    from ..mcp_server import main as mcp_main

    mcp_main()


@app.command()
def observe(
    kind: str = typer.Argument(
        ...,
        help="Event kind: session-start, user-prompt, post-tool-use, pre-compact, session-end",
    ),
    content: str = typer.Argument("", help="Event content (reads stdin if empty)"),
    cwd: str = typer.Option("", "--cwd", help=_HELP_WORKDIR),
    session: str = typer.Option("", "--session", "-s", help=_HELP_SESSION),
    agent: str = typer.Option("manual", "--agent", "-a", help="Agent name"),
) -> None:
    """Send a lifecycle observation to the server. CLI fallback for hooks."""

    import json
    import sys
    import urllib.error
    import urllib.request

    from ..daemon import ensure_server, get_server_url

    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        if not content:
            content = ""

    ensure_server()
    url = get_server_url()

    payload = {
        "kind": kind,
        "session_id": session or "cli-obs",
        "agent": agent,
        "cwd": cwd or str(Path.cwd()),
        "body": content[:10000] if content else None,
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("MEM0RY_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{url}/hook",
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            result = json.loads(resp.read())
            typer.echo(f"Observed: {result.get('id', '?')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        typer.echo(f"Error {e.code}: {body}", err=True)
    except (urllib.error.URLError, OSError) as e:
        typer.echo(f"Server not reachable: {e}", err=True)


def _handoff_begin(work_dir: str, summary: str, session: str) -> None:
    from ..db.store import begin_handoff
    from ..utils.git_context import resolve_full_context

    config = MemoryConfig()
    db_path = Path(config.db_path)
    resolved = resolve_full_context(Path(work_dir), session or None)

    ho_id = begin_handoff(
        db_path,
        session_id=resolved.get("session_id") or "cli-handoff",
        from_agent="cli",
        summary=summary,
        project_id=resolved.get("project_id"),
        project_path=resolved.get("project_path"),
        context=resolved.get("context"),
    )
    typer.echo(f"Handoff {ho_id} created.")


def _handoff_accept(work_dir: str) -> None:
    from ..db.store import accept_handoff
    from ..utils.git_context import resolve_full_context

    config = MemoryConfig()
    db_path = Path(config.db_path)
    resolved = resolve_full_context(Path(work_dir))

    ho = accept_handoff(
        db_path,
        project_id=resolved.get("project_id"),
        accepted_by="cli",
    )
    if not ho:
        typer.echo("No pending handoff found.")
        return

    typer.echo(f"Handoff from {ho['from_agent']} ({ho['created_at'][:10]}):")
    typer.echo(f"  {ho['summary']}")
    if ho.get("open_questions"):
        typer.echo("\n  Open questions:")
        for q in ho["open_questions"]:
            typer.echo(f"    - {q}")
    if ho.get("next_steps"):
        typer.echo("\n  Next steps:")
        for s in ho["next_steps"]:
            typer.echo(f"    - {s}")


def _handoff_status() -> None:
    from ..daemon import server_status

    info = server_status()
    if info["running"]:
        typer.echo(f"Server running (pid {info['pid']}) at {info['url']}")
        if info.get("health"):
            typer.echo(f"Health: {info['health']}")
    else:
        typer.echo("Server not running.")


@app.command()
def handoff(
    action: str = typer.Argument(..., help="Action: begin, accept, status"),
    cwd: str = typer.Option("", "--cwd", help=_HELP_WORKDIR),
    summary: str = typer.Option("", "--summary", "-m", help="Handoff summary"),
    session: str = typer.Option("", "--session", "-s", help=_HELP_SESSION),
) -> None:
    """Manage cross-agent handoffs: begin, accept, or check status."""

    work_dir = cwd or str(Path.cwd())

    if action == "begin":
        if not summary:
            typer.echo("Summary is required for 'begin'. Use --summary.", err=True)
            raise typer.Exit(code=1)
        _handoff_begin(work_dir, summary, session)
    elif action == "accept":
        _handoff_accept(work_dir)
    elif action == "status":
        _handoff_status()
    else:
        typer.echo(f"Unknown action: {action}. Use: begin, accept, status", err=True)
        raise typer.Exit(code=1)


@app.command()
def backup(
    to: Path = typer.Option(
        Path(""), "--to", "-t", help="Output tarball path (default: data/mem0ry-backup-DATE.tar.gz)"
    ),
) -> None:
    """Backup database and conversations to a tarball."""

    import tarfile

    config = MemoryConfig()
    db_path = Path(config.db_path)
    conv_dir = Path(config.conversations_dir)

    if not db_path.exists() and not conv_dir.exists():
        typer.echo("Nothing to backup — no database or conversations found.", err=True)
        raise typer.Exit(code=1)

    today = date.today().isoformat()
    default_name = Path(f"data/mem0ry-backup-{today}.tar.gz")
    dest = to if str(to) else default_name
    dest.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(dest, "w:gz") as tar:
        if db_path.exists():
            tar.add(db_path, arcname=db_path.name)
            typer.echo(f"  Added: {db_path}")
        if conv_dir.exists():
            tar.add(conv_dir, arcname=conv_dir.name)
            typer.echo(f"  Added: {conv_dir}")

    size_kb = dest.stat().st_size / 1024
    typer.echo(f"Backup saved to {dest} ({size_kb:.1f} KB)")


@app.command()
def restore(
    fr: Path = typer.Option(
        Path(""), "--from", "-f", help="Tarball to restore from"
    ),
) -> None:
    """Restore database and conversations from a tarball backup."""

    import tarfile

    if not fr.exists():
        typer.echo(f"File not found: {fr}", err=True)
        raise typer.Exit(code=1)

    config = MemoryConfig()
    data_dir = Path(config.db_path).parent

    with tarfile.open(fr, "r:gz") as tar:
        members = tar.getmembers()
        typer.echo(f"Restoring {len(members)} items...")
        tar.extractall(path=data_dir, filter="data")

    typer.echo(f"Restored to {data_dir}")
