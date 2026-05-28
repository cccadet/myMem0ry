from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ._app import app


@app.command()
def migrate(
    conversations: Path = Path(""),
    reprocess: bool = typer.Option(
        False, "--reprocess", help="Drop DB and reingest all .md files into v3 schema"
    ),
) -> None:
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
