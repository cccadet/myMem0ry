from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from ..config import MemoryConfig
from ._app import app


@app.command()
def decay(
    days: int = typer.Option(90, "--days", "-d", help="Legacy — ignored, kept for compat"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without deleting"),
) -> None:
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
