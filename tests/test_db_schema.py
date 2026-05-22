"""Tests for db.schema — table creation and indexing."""

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
    assert row["value"] == "2"
    conn.close()


def test_memories_columns(tmp_path: Path) -> None:
    db = tmp_path / "cols.db"
    conn = get_connection(db)
    init_schema(conn)

    cols = conn.execute("PRAGMA table_info(memories)").fetchall()
    names = [row["name"] for row in cols]
    assert "id" in names
    assert "content" in names
    assert "scope" in names
    assert "project_path" in names
    assert "session_id" in names
    assert "source" in names
    assert "tags" in names
    assert "title" in names
    assert "created_at" in names
    assert "file_path" in names
    conn.close()
