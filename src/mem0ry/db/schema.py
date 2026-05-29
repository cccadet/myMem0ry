"""Schema definition and initialization for the memories database."""

from __future__ import annotations

import sqlite3

_SCHEMA_VERSION = 6

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
    last_accessed_at TEXT,
    salience REAL NOT NULL DEFAULT 0.5,
    pinned INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    grace_until TEXT
)
"""

_CREATE_OBSERVATIONS = """
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    agent TEXT,
    cwd TEXT,
    project_id TEXT,
    title TEXT,
    body TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_HANDOFFS = """
CREATE TABLE IF NOT EXISTS handoffs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    from_agent TEXT NOT NULL,
    project_id TEXT,
    project_path TEXT,
    context TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    summary TEXT NOT NULL,
    open_questions TEXT,
    next_steps TEXT,
    accepted_by TEXT,
    accepted_at TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
)
"""

_CREATE_METADATA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    agent TEXT,
    details TEXT,
    created_at TEXT NOT NULL
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

_INDEX_OBS_SESSION = """
CREATE INDEX IF NOT EXISTS idx_obs_session
ON observations(session_id)
"""

_INDEX_OBS_KIND = """
CREATE INDEX IF NOT EXISTS idx_obs_kind
ON observations(kind)
"""

_INDEX_OBS_CREATED = """
CREATE INDEX IF NOT EXISTS idx_obs_created
ON observations(created_at)
"""

_INDEX_HANDOFFS_STATUS = """
CREATE INDEX IF NOT EXISTS idx_handoffs_status
ON handoffs(status)
"""

_INDEX_HANDOFFS_PROJECT = """
CREATE INDEX IF NOT EXISTS idx_handoffs_project
ON handoffs(project_id)
"""

_INDEX_HANDOFFS_EXPIRES = """
CREATE INDEX IF NOT EXISTS idx_handoffs_expires
ON handoffs(expires_at)
"""

_INDEX_AUDIT_ACTION = """
CREATE INDEX IF NOT EXISTS idx_audit_action
ON audit_log(action)
"""

_INDEX_AUDIT_TARGET = """
CREATE INDEX IF NOT EXISTS idx_audit_target
ON audit_log(target_type, target_id)
"""

_INDEX_AUDIT_CREATED = """
CREATE INDEX IF NOT EXISTS idx_audit_created
ON audit_log(created_at)
"""


_EXTRA_COLUMNS: list[tuple[str, str]] = [
    ("project_id", "TEXT"),
    ("project_path", "TEXT"),
    ("context", "TEXT"),
    ("session_id", "TEXT"),
    ("memory_type", "TEXT NOT NULL DEFAULT 'log'"),
    ("source", "TEXT NOT NULL DEFAULT 'manual'"),
    ("tags", "TEXT NOT NULL DEFAULT '[]'"),
    ("title", "TEXT"),
    ("updated_at", "TEXT"),
    ("file_path", "TEXT"),
    ("access_count", "INTEGER NOT NULL DEFAULT 0"),
    ("last_accessed_at", "TEXT"),
    ("salience", "REAL NOT NULL DEFAULT 0.5"),
    ("pinned", "INTEGER NOT NULL DEFAULT 0"),
    ("deleted_at", "TEXT"),
    ("grace_until", "TEXT"),
]


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()
    }
    for col_name, col_def in _EXTRA_COLUMNS:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_def}")


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist.

    Uses PRAGMA user_version as a fast read-only gate — skips all DDL when the
    schema is already at the current version, avoiding write-lock contention in
    multi-process setups.
    """
    v = conn.execute("PRAGMA user_version").fetchone()[0]
    if v >= _SCHEMA_VERSION:
        return

    for sql in (
        _CREATE_MEMORIES,
        _CREATE_OBSERVATIONS,
        _CREATE_HANDOFFS,
        _CREATE_METADATA,
        _CREATE_AUDIT_LOG,
    ):
        conn.execute(sql)
    _ensure_columns(conn)
    for sql in (
        _INDEX_SCOPE,
        _INDEX_PROJECT_ID,
        _INDEX_PROJECT_PATH,
        _INDEX_CONTEXT,
        _INDEX_SESSION,
        _INDEX_CREATED,
        _INDEX_TYPE,
        _INDEX_OBS_SESSION,
        _INDEX_OBS_KIND,
        _INDEX_OBS_CREATED,
        _INDEX_HANDOFFS_STATUS,
        _INDEX_HANDOFFS_PROJECT,
        _INDEX_HANDOFFS_EXPIRES,
        _INDEX_AUDIT_ACTION,
        _INDEX_AUDIT_TARGET,
        _INDEX_AUDIT_CREATED,
    ):
        conn.execute(sql)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
        ("version", str(_SCHEMA_VERSION)),
    )
    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    conn.commit()
