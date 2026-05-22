"""Schema definition and initialization for the memories database."""

from __future__ import annotations

import sqlite3

_SCHEMA_VERSION = 2

_CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    project_path TEXT,
    session_id TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    tags TEXT NOT NULL DEFAULT '[]',
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    file_path TEXT
)
"""

_CREATE_METADATA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_INDEX_SCOPE = """
CREATE INDEX IF NOT EXISTS idx_memories_scope
ON memories(scope)
"""

_INDEX_PROJECT = """
CREATE INDEX IF NOT EXISTS idx_memories_project
ON memories(project_path)
"""

_INDEX_SESSION = """
CREATE INDEX IF NOT EXISTS idx_memories_session
ON memories(session_id)
"""

_INDEX_CREATED = """
CREATE INDEX IF NOT EXISTS idx_memories_created
ON memories(created_at)
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist."""
    for sql in (
        _CREATE_MEMORIES,
        _CREATE_METADATA,
        _INDEX_SCOPE,
        _INDEX_PROJECT,
        _INDEX_SESSION,
        _INDEX_CREATED,
    ):
        conn.execute(sql)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
        ("version", str(_SCHEMA_VERSION)),
    )
    conn.commit()
