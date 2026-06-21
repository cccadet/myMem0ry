"""Tests for schema v9 fts_rowid migration and DoltLite compatibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import _SCHEMA_VERSION, init_schema, next_fts_rowid
from mem0ry.db.store import create_memory, search_memories


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_schema_version_is_9(db: Path) -> None:
    conn = get_connection(db)
    try:
        assert _SCHEMA_VERSION == 9
        row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        assert row["value"] == "9"
    finally:
        conn.close()


def test_memories_table_has_fts_rowid(db: Path) -> None:
    conn = get_connection(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()}
        assert "fts_rowid" in cols
    finally:
        conn.close()


def test_create_memory_populates_fts_rowid(db: Path) -> None:
    mem_id = create_memory(db, content="JWT authentication flow", title="Auth")
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT fts_rowid FROM memories WHERE id = ?", (mem_id,)
        ).fetchone()
        assert row["fts_rowid"] is not None
        assert row["fts_rowid"] > 0
    finally:
        conn.close()


def test_fts_trigger_indexes_memory(db: Path) -> None:
    create_memory(db, content="autenticação JWT com refresh token", title="Auth")
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT rowid FROM memories_fts WHERE content MATCH 'autenticacao'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_fts_search_returns_memory(db: Path) -> None:
    create_memory(db, content="configuracao de banco de dados SQLite", title="DB")
    results = search_memories(db, query="banco", top_k=10)
    assert len(results) == 1
    assert "banco" in results[0]["content"].lower()


def test_next_fts_rowid_is_monotonic(db: Path) -> None:
    conn = get_connection(db)
    try:
        first = next_fts_rowid(conn)
        create_memory(db, content="first", title="First")
        second = next_fts_rowid(conn)
        assert second == first + 1
    finally:
        conn.close()


def test_v8_to_v9_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = get_connection(db_path)
    try:
        # Build a v8 schema manually (no fts_rowid, triggers using rowid).
        conn.execute(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'global',
                created_at TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                memory_type TEXT NOT NULL DEFAULT 'log',
                source TEXT NOT NULL DEFAULT 'manual',
                deleted_at TEXT,
                superseded_by TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE memories_fts USING fts5(
                title, content, tags,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
        conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_meta(key, value) VALUES('version', '8')")
        conn.execute("PRAGMA user_version = 8")
        conn.execute(
            "INSERT INTO memories(id, content, scope, created_at) VALUES('legacy1', 'old memory', 'global', '2025-01-01')"
        )
        conn.commit()
    finally:
        conn.close()

    # Re-open and run init_schema to trigger v9 migration.
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        assert row["value"] == "9"

        legacy = conn.execute(
            "SELECT fts_rowid FROM memories WHERE id = 'legacy1'"
        ).fetchone()
        assert legacy["fts_rowid"] is not None
        assert legacy["fts_rowid"] > 0

        # FTS should be rebuilt with explicit fts_rowid.
        fts = conn.execute(
            "SELECT rowid FROM memories_fts WHERE content MATCH 'memory'"
        ).fetchone()
        assert fts is not None
        assert fts["rowid"] == legacy["fts_rowid"]
    finally:
        conn.close()
