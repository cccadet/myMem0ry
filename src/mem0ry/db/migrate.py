"""Migrate existing .md conversation files into the structured memories database."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path

from .connection import get_connection
from .schema import init_schema


_HEADER_RE = re.compile(
    r"^#\s+(?P<title>.+?)\s*$\n"
    r"^>\s*id:\s*(?P<id>\S+)\s*\|\s*date:\s*(?P<date>\S+)",
    re.MULTILINE,
)


def _parse_md_file(path: Path) -> dict | None:
    """Extract metadata from a myMem0ry .md file header."""
    text = path.read_text(encoding="utf-8")
    match = _HEADER_RE.search(text)
    if not match:
        return None
    return {
        "id": match.group("id"),
        "title": match.group("title").strip(),
        "date": match.group("date"),
        "content": text,
    }


def migrate_v1_to_v2(conversations_dir: Path, db_path: Path) -> dict:
    """Migrate .md files from conversations_dir into the memories table.

    Returns a dict with stats: total, migrated, skipped.
    """
    if not conversations_dir.exists():
        return {"total": 0, "migrated": 0, "skipped": 0}

    conn = get_connection(db_path)
    init_schema(conn)

    md_files = sorted(conversations_dir.rglob("*.md"))
    stats = {"total": len(md_files), "migrated": 0, "skipped": 0}

    for md_path in md_files:
        rel_path = str(md_path.relative_to(conversations_dir))
        existing = conn.execute(
            "SELECT id FROM memories WHERE file_path = ?", (rel_path,)
        ).fetchone()
        if existing:
            stats["skipped"] += 1
            continue

        parsed = _parse_md_file(md_path)
        if not parsed:
            stats["skipped"] += 1
            continue

        mem_id = str(uuid.uuid4())
        created_at = parsed["date"]
        try:
            datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            created_at = date.today().isoformat()

        conn.execute(
            "INSERT INTO memories(id, content, scope, source, tags, title, created_at, file_path) "
            "VALUES(?, ?, 'global', 'import', '[]', ?, ?, ?)",
            (mem_id, parsed["content"], parsed["title"], created_at, rel_path),
        )
        stats["migrated"] += 1

    conn.commit()
    conn.close()
    return stats
