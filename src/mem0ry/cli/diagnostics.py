from __future__ import annotations

from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any

import typer

from ..config import MemoryConfig
from ._app import app


@app.command(help="Print the installed myMem0ry version")
def version() -> None:
    try:
        typer.echo(f"mymem0ry {pkg_version('mymem0ry')}")
    except Exception:
        typer.echo("mymem0ry (unknown version)")


@app.command(help="Show database statistics (memory counts, sizes)")
def stats() -> None:
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


@app.command(help="Diagnose configuration, environment and server health")
def doctor() -> None:
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


@app.command(help="List known projects in the database")
def projects() -> None:
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
