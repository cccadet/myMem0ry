from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ._app import _HELP_SESSION, _HELP_WORKDIR, app


@app.command()
def context(
    cwd: str = typer.Option(
        "", "--cwd", help="Working directory to resolve context from"
    ),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of memories to load"),
    session: str = typer.Option("", "--session", "-s", help=_HELP_SESSION),
) -> None:
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
