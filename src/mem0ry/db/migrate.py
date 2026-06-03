"""Migrate existing .md conversation files into the structured memories database."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path

from .connection import get_connection
from .schema import init_schema

_VERSION_SQL = "SELECT value FROM schema_meta WHERE key='version'"
_SET_VERSION_SQL = "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)"


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


def _guess_memory_type(title: str) -> str:
    lower = title.lower()
    if any(kw in lower for kw in ("decision", "architecture", "decisao")):
        return "decision"
    if any(kw in lower for kw in ("fact", "preferencia", "preference", "stack")):
        return "fact"
    if any(kw in lower for kw in ("pattern", "padrao")):
        return "pattern"
    return "log"


def migrate_v1_to_v2(conversations_dir: Path, db_path: Path) -> dict:
    """Migrate .md files from conversations_dir into the memories table (v2).

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


def migrate_v2_to_v3(conversations_dir: Path, db_path: Path) -> dict:
    """Migrate .md files into v3 schema (drop + reingest).

    Drops the existing database and re-creates with v3 schema.
    All .md files are re-ingested with project_id and memory_type heuristics.

    Returns a dict with stats: total, migrated, skipped.
    """
    if db_path.exists():
        db_path.unlink()

    conn = get_connection(db_path)
    init_schema(conn)

    if not conversations_dir.exists():
        conn.close()
        return {"total": 0, "migrated": 0, "skipped": 0}

    md_files = sorted(conversations_dir.rglob("*.md"))
    result = {"total": len(md_files), "migrated": 0, "skipped": 0}

    for md_path in md_files:
        rel_path = str(md_path.relative_to(conversations_dir))
        parsed = _parse_md_file(md_path)
        if not parsed:
            result["skipped"] += 1
            continue

        mem_id = uuid.uuid4().hex[:12]
        created_at = parsed["date"]
        try:
            datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            created_at = date.today().isoformat()

        memory_type = _guess_memory_type(parsed["title"])

        conn.execute(
            "INSERT INTO memories(id, content, scope, memory_type, source, tags, "
            "title, created_at, file_path, access_count, last_accessed_at) "
            "VALUES(?, ?, 'global', ?, 'import', '[]', ?, ?, ?, 0, ?)",
            (
                mem_id,
                parsed["content"],
                memory_type,
                parsed["title"],
                created_at,
                rel_path,
                created_at,
            ),
        )
        result["migrated"] += 1

    conn.commit()
    conn.close()
    return result


def migrate_v3_to_v4(db_path: Path) -> dict:
    """Upgrade v3 schema to v4: add observations and handoffs tables.

    Uses CREATE TABLE IF NOT EXISTS, so existing data is preserved.
    Returns a dict with the new schema version.
    """
    conn = get_connection(db_path)
    init_schema(conn)

    version_row = conn.execute(_VERSION_SQL).fetchone()
    old_version = int(version_row["value"]) if version_row else 3

    conn.close()
    return {"old_version": old_version, "new_version": 4}


def migrate_v4_to_v5(db_path: Path) -> dict:
    """Upgrade v4 schema to v5: add salience, pinned, deleted_at, grace_until.

    Retention tier is derived from memory_type (no column needed).
    Existing facts/decisions are auto-pinned; salience is computed for all.
    """
    conn = get_connection(db_path)

    version_row = conn.execute(_VERSION_SQL).fetchone()
    old_version = int(version_row["value"]) if version_row else 4

    new_cols = [
        ("salience", "REAL NOT NULL DEFAULT 0.5"),
        ("pinned", "INTEGER NOT NULL DEFAULT 0"),
        ("deleted_at", "TEXT"),
        ("grace_until", "TEXT"),
    ]
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(memories)").fetchall()
    }
    for col_name, col_def in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_def}")

    conn.execute(
        "UPDATE memories SET pinned = 1 WHERE memory_type IN ('fact', 'decision') AND pinned = 0"
    )
    conn.commit()
    conn.close()

    from .retention import update_salience_for_all

    update_salience_for_all(db_path)

    conn = get_connection(db_path)
    conn.execute(
        _SET_VERSION_SQL,
        ("version", "5"),
    )
    conn.commit()
    conn.close()

    return {"old_version": old_version, "new_version": 5}


def migrate_v5_to_v6(db_path: Path) -> dict:
    """Upgrade v5 schema to v6: add audit_log table.

    Uses CREATE TABLE IF NOT EXISTS, so existing data is preserved.
    """
    conn = get_connection(db_path)
    init_schema(conn)

    version_row = conn.execute(_VERSION_SQL).fetchone()
    old_version = int(version_row["value"]) if version_row else 5

    conn.execute(
        _SET_VERSION_SQL,
        ("version", "6"),
    )
    conn.commit()
    conn.close()

    return {"old_version": old_version, "new_version": 6}


def migrate_v6_to_v7(db_path: Path) -> dict:
    """Upgrade v6 schema to v7: add superseded_by column for fact evolution."""
    conn = get_connection(db_path)

    version_row = conn.execute(_VERSION_SQL).fetchone()
    old_version = int(version_row["value"]) if version_row else 6

    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()
    }
    if "superseded_by" not in existing:
        conn.execute("ALTER TABLE memories ADD COLUMN superseded_by TEXT")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_superseded ON memories(superseded_by)"
    )
    conn.execute(
        _SET_VERSION_SQL,
        ("version", "7"),
    )
    conn.commit()
    conn.close()

    return {"old_version": old_version, "new_version": 7}


def migrate_v7_to_v8(db_path: Path) -> dict:
    """Upgrade v7 schema to v8: add FTS5 index + triggers on memories."""
    from .schema import (
        _CREATE_MEMORIES_FTS,
        _TRIGGER_FTS_INSERT,
        _TRIGGER_FTS_UPDATE,
        _TRIGGER_FTS_DELETE,
    )

    conn = get_connection(db_path)
    init_schema(conn)

    version_row = conn.execute(_VERSION_SQL).fetchone()
    old_version = int(version_row["value"]) if version_row else 7

    conn.execute(_CREATE_MEMORIES_FTS)

    conn.execute(
        "INSERT INTO memories_fts(rowid, title, content, tags) "
        "SELECT rowid, COALESCE(title, ''), content, tags "
        "FROM memories WHERE deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by = '')"
    )

    for sql in (
        _TRIGGER_FTS_INSERT,
        _TRIGGER_FTS_UPDATE,
        _TRIGGER_FTS_DELETE,
    ):
        conn.execute(sql)

    conn.execute(_SET_VERSION_SQL, ("version", "8"))
    conn.execute("PRAGMA user_version = 8")
    conn.commit()
    conn.close()

    return {"old_version": old_version, "new_version": 8}
