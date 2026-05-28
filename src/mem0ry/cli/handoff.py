from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ._app import _HELP_SESSION, _HELP_WORKDIR, app


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
