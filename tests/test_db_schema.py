"""Tests for db.schema — table creation and indexing (v3)."""

from __future__ import annotations

from pathlib import Path

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema


def test_init_schema_creates_tables(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    conn = get_connection(db)
    init_schema(conn)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [row["name"] for row in tables]
    assert "memories" in names
    assert "schema_meta" in names
    conn.close()


def test_init_schema_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "idem.db"
    conn = get_connection(db)
    init_schema(conn)
    init_schema(conn)

    count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
    assert count == 0
    conn.close()


def test_init_schema_version(tmp_path: Path) -> None:
    db = tmp_path / "ver.db"
    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    assert row["value"] == "6"
    conn.close()


def test_memories_columns(tmp_path: Path) -> None:
    db = tmp_path / "cols.db"
    conn = get_connection(db)
    init_schema(conn)

    cols = conn.execute("PRAGMA table_info(memories)").fetchall()
    names = [row["name"] for row in cols]
    expected = [
        "id",
        "content",
        "scope",
        "project_id",
        "project_path",
        "context",
        "session_id",
        "memory_type",
        "source",
        "tags",
        "title",
        "created_at",
        "updated_at",
        "file_path",
        "access_count",
        "last_accessed_at",
        "salience",
        "pinned",
        "deleted_at",
        "grace_until",
    ]
    for col in expected:
        assert col in names, f"Missing column: {col}"
    conn.close()
