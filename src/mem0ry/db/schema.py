"""Schema definition and initialization for the memories database."""

from __future__ import annotations

import sqlite3

_SCHEMA_VERSION = 3

_CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    project_id TEXT,
    project_path TEXT,
    context TEXT,
    session_id TEXT,
    memory_type TEXT NOT NULL DEFAULT 'log',
    source TEXT NOT NULL DEFAULT 'manual',
    tags TEXT NOT NULL DEFAULT '[]',
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    file_path TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT
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

_INDEX_PROJECT_ID = """
CREATE INDEX IF NOT EXISTS idx_memories_project_id
ON memories(project_id)
"""

_INDEX_PROJECT_PATH = """
CREATE INDEX IF NOT EXISTS idx_memories_project_path
ON memories(project_path)
"""

_INDEX_CONTEXT = """
CREATE INDEX IF NOT EXISTS idx_memories_context
ON memories(context)
"""

_INDEX_SESSION = """
CREATE INDEX IF NOT EXISTS idx_memories_session
ON memories(session_id)
"""

_INDEX_CREATED = """
CREATE INDEX IF NOT EXISTS idx_memories_created
ON memories(created_at)
"""

_INDEX_TYPE = """
CREATE INDEX IF NOT EXISTS idx_memories_type
ON memories(memory_type)
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist."""
    for sql in (
        _CREATE_MEMORIES,
        _CREATE_METADATA,
        _INDEX_SCOPE,
        _INDEX_PROJECT_ID,
        _INDEX_PROJECT_PATH,
        _INDEX_CONTEXT,
        _INDEX_SESSION,
        _INDEX_CREATED,
        _INDEX_TYPE,
    ):
        conn.execute(sql)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
        ("version", str(_SCHEMA_VERSION)),
    )
    conn.commit()
