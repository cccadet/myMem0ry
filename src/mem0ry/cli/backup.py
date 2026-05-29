from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from ..config import MemoryConfig
from ._app import app


@app.command(help="Back up the database and conversations to a tarball")
def backup(
    to: Path = typer.Option(
        Path(""), "--to", "-t", help="Output tarball path (default: data/mem0ry-backup-DATE.tar.gz)"
    ),
) -> None:
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


@app.command(help="Restore the database and conversations from a tarball")
def restore(
    fr: Path = typer.Option(
        Path(""), "--from", "-f", help="Tarball to restore from"
    ),
) -> None:
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
