"""DoltLite version-control helpers for the memories database."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from .connection import is_doltlite_db

logger = logging.getLogger(__name__)


class DoltLiteError(Exception):
    """Raised when a DoltLite operation fails."""


DEFAULT_COMMIT_MESSAGE = "auto: memory write"


def _dolt_call(conn: sqlite3.Connection, sql: str) -> Any:
    """Execute a DoltLite function call and return its scalar result."""
    try:
        result = conn.execute(sql).fetchone()
        return result[0] if result else None
    except sqlite3.OperationalError as exc:
        raise DoltLiteError(f"DoltLite call failed: {sql}") from exc


def auto_commit(conn: sqlite3.Connection, message: str = DEFAULT_COMMIT_MESSAGE) -> str | None:
    """Stage all changes and commit when running on a DoltLite database.

    Returns the commit hash, or None when the database is plain SQLite.
    """
    if not is_doltlite_db(conn):
        return None

    _dolt_call(conn, "SELECT dolt_add('-A')")
    commit_hash = _dolt_call(conn, f"SELECT dolt_commit('-m', '{message}')")
    logger.debug("DoltLite auto-commit: %s", commit_hash)
    return commit_hash


def maybe_auto_commit(conn: sqlite3.Connection) -> None:
    """Create a DoltLite commit after a write when auto-sync is enabled."""
    import os

    if os.environ.get("MEM0RY_SYNC_AUTO_COMMIT", "1") == "1":
        auto_commit(conn)


def ensure_dolt_config(conn: sqlite3.Connection, name: str, email: str) -> None:
    """Set DoltLite user.name and user.email if not already configured."""
    if not is_doltlite_db(conn):
        return

    _dolt_call(conn, f"SELECT dolt_config('user.name', '{name}')")
    _dolt_call(conn, f"SELECT dolt_config('user.email', '{email}')")


def init_dolt_remote(
    conn: sqlite3.Connection,
    remote_url: str,
    remote_name: str = "origin",
    branch: str = "main",
) -> None:
    """Add a DoltLite remote and configure the active branch upstream."""
    if not is_doltlite_db(conn):
        raise DoltLiteError("Database is not a DoltLite database")

    ensure_dolt_config(conn, "myMem0ry", "sync@mymem0ry.local")
    _dolt_call(conn, f"SELECT dolt_remote('add', '{remote_name}', '{remote_url}')")
    _dolt_call(conn, f"SELECT dolt_branch('{branch}')")
    _dolt_call(conn, f"SELECT dolt_checkout('{branch}')")


def dolt_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return DoltLite working-set status."""
    if not is_doltlite_db(conn):
        return {"engine": "sqlite", "clean": True}

    status_table = _dolt_call(conn, "SELECT dolt_status()")
    log = conn.execute("SELECT commit_hash, message FROM dolt_log LIMIT 5").fetchall()
    branch = _dolt_call(conn, "SELECT active_branch()")
    return {
        "engine": "doltlite",
        "branch": branch,
        "status": status_table,
        "recent_commits": [dict(row) for row in log],
    }


def dolt_push(
    conn: sqlite3.Connection,
    remote: str = "origin",
    branch: str = "main",
) -> str | None:
    """Push the current branch to a DoltLite remote."""
    if not is_doltlite_db(conn):
        return None

    return _dolt_call(conn, f"SELECT dolt_push('{remote}', '{branch}')")


def dolt_pull(
    conn: sqlite3.Connection,
    remote: str = "origin",
    branch: str = "main",
) -> str | None:
    """Pull and merge a DoltLite remote branch into the current branch."""
    if not is_doltlite_db(conn):
        return None

    return _dolt_call(conn, f"SELECT dolt_pull('{remote}', '{branch}')")


def resolve_conflicts_ours(conn: sqlite3.Connection, table: str) -> None:
    """Resolve DoltLite conflicts for ``table`` keeping our version."""
    if not is_doltlite_db(conn):
        return

    _dolt_call(conn, f"SELECT dolt_conflicts_resolve('--ours', '{table}')")


def init_dolt_db(db_path: Path, remote_url: str | None = None) -> sqlite3.Connection:
    """Create or open a DoltLite-backed database and optionally add a remote."""
    import os

    # Force DoltLite engine selection for new databases.
    os.environ["MEM0RY_SYNC_ENGINE"] = "doltlite"

    from .connection import get_connection

    conn = get_connection(db_path)
    if not is_doltlite_db(conn):
        raise DoltLiteError(
            "Failed to initialize DoltLite database. "
            "Is the DoltLite binding installed and Python compiled with shared _sqlite3?"
        )

    ensure_dolt_config(conn, "myMem0ry", "sync@mymem0ry.local")
    if remote_url:
        init_dolt_remote(conn, remote_url)
    return conn
