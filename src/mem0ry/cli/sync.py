"""DoltLite sync commands for myMem0ry."""

from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ..db.connection import get_connection, is_doltlite_db
from ..db.doltlite_sync import (
    DoltLiteError,
    dolt_pull,
    dolt_push,
    dolt_status,
    ensure_dolt_config,
    init_dolt_db,
    init_dolt_remote,
)
from ..db.schema import init_schema
from ._app import app

sync_app = typer.Typer(help="DoltLite version-control sync (experimental)")
app.add_typer(sync_app, name="sync")


@sync_app.command(help="Initialize a DoltLite database and optional remote")
def init(
    remote: str = typer.Option(
        None, "--remote", "-r", help="Remote URL (file:// or http://)"
    ),
    branch: str = typer.Option("main", "--branch", "-b", help="Default branch"),
) -> None:
    config = MemoryConfig()
    db_path = Path(config.db_path)

    if db_path.exists() and not is_doltlite_db(get_connection(db_path)):
        typer.echo(
            "A plain SQLite database already exists. "
            "Convert it first or choose a different DB_PATH.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        conn = init_dolt_db(db_path, remote_url=remote)
        if remote:
            init_dolt_remote(conn, remote, branch=branch)
        init_schema(conn)
        conn.commit()
        conn.close()
        typer.echo(f"DoltLite database initialized at {db_path}")
        if remote:
            typer.echo(f"Remote: {remote} (branch: {branch})")
    except DoltLiteError as exc:
        typer.echo(f"Failed to initialize DoltLite: {exc}", err=True)
        raise typer.Exit(code=1)


@sync_app.command(help="Push the current branch to the configured remote")
def push(
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch to push"),
) -> None:
    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found.", err=True)
        raise typer.Exit(code=1)

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        if not is_doltlite_db(conn):
            typer.echo("Sync is only available for DoltLite databases.", err=True)
            raise typer.Exit(code=1)

        ensure_dolt_config(conn, "myMem0ry", "sync@mymem0ry.local")
        target_branch = branch or config.sync_branch
        result = dolt_push(conn, remote, target_branch)
        conn.commit()
        typer.echo(f"Pushed {target_branch} to {remote}: {result}")
    finally:
        conn.close()


@sync_app.command(help="Pull and merge changes from the configured remote")
def pull(
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch to pull"),
) -> None:
    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found.", err=True)
        raise typer.Exit(code=1)

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        if not is_doltlite_db(conn):
            typer.echo("Sync is only available for DoltLite databases.", err=True)
            raise typer.Exit(code=1)

        target_branch = branch or config.sync_branch
        result = dolt_pull(conn, remote, target_branch)
        conn.commit()
        typer.echo(f"Pulled {target_branch} from {remote}: {result}")
    finally:
        conn.close()


@sync_app.command(help="Show sync status and recent commits")
def status() -> None:
    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("Database not found.", err=True)
        raise typer.Exit(code=1)

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        info = dolt_status(conn)
        if info["engine"] == "sqlite":
            typer.echo("Running on plain SQLite (DoltLite not enabled).")
            return

        typer.echo(f"Engine: {info['engine']}")
        typer.echo(f"Branch: {info['branch']}")
        typer.echo(f"Status: {info['status']}")
        if info["recent_commits"]:
            typer.echo("Recent commits:")
            for commit in info["recent_commits"]:
                typer.echo(f"  {commit['commit_hash']}: {commit['message']}")
    finally:
        conn.close()
