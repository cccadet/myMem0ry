from __future__ import annotations

import json
from pathlib import Path

import typer

from ..config import MemoryConfig
from ..db.store import export_memories, export_handoffs, import_memories, import_handoffs
from ._app import app


@app.command(name="export", help="Export memories and handoffs to a JSON file")
def export_cmd(
    output: Path = typer.Option(
        Path(""), "--output", "-o", help="Output file path (default: mem0ry-export.json)"
    ),
    project_id: str = typer.Option("", "--project-id", "-p", help="Filter by project ID"),
    scope: str = typer.Option("", "--scope", "-s", help="Filter by scope (global/project/context/session)"),
    all_items: bool = typer.Option(False, "--all", "-a", help="Export everything"),
) -> None:
    config = MemoryConfig()
    db_path = Path(config.db_path)

    if not db_path.exists():
        typer.echo("No database found.", err=True)
        raise typer.Exit(code=1)

    dest = output if str(output) else Path("mem0ry-export.json")

    filters: dict = {}
    if project_id:
        filters["project_id"] = project_id
    if scope:
        filters["scope"] = scope

    data = export_memories(db_path, **filters)

    pid = project_id or None
    handoffs = export_handoffs(db_path, project_id=pid)
    if handoffs:
        data["handoffs"] = handoffs

    mem_count = len(data.get("memories", []))
    ho_count = len(data.get("handoffs", []))

    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    size_kb = dest.stat().st_size / 1024
    typer.echo(f"Exported {mem_count} memories, {ho_count} handoffs to {dest} ({size_kb:.1f} KB)")


@app.command(name="import", help="Import memories and handoffs from a JSON export file")
def import_cmd(
    source: Path = typer.Argument(..., help="Export JSON file to import"),
    project_id_override: str = typer.Option(
        "", "--project-id", "-p", help="Override project ID for imported items"
    ),
) -> None:
    if not source.exists():
        typer.echo(f"File not found: {source}", err=True)
        raise typer.Exit(code=1)

    config = MemoryConfig()
    db_path = Path(config.db_path)

    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        typer.echo(f"Invalid JSON: {e}", err=True)
        raise typer.Exit(code=1)

    pid = project_id_override or None
    mem_result = import_memories(db_path, data, project_id_override=pid)

    ho_result = {"imported": 0, "skipped": 0}
    if data.get("handoffs"):
        ho_result = import_handoffs(db_path, data["handoffs"], project_id_override=pid)

    typer.echo(
        f"Imported: {mem_result['imported']} memories, {ho_result['imported']} handoffs. "
        f"Skipped (duplicates): {mem_result['skipped']} memories, {ho_result['skipped']} handoffs."
    )
