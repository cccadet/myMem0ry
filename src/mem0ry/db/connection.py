"""SQLite connection factory for the memories database."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import sqlite_vec  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vec extension."""
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    except Exception as exc:
        logger.debug("sqlite_vec.load failed: %s", exc)
        raise
    finally:
        conn.enable_load_extension(False)


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with sqlite-vec loaded.

    Creates parent directories if needed. The connection uses WAL journal mode
    for concurrent read/write support.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")

    _load_sqlite_vec(conn)
    conn.row_factory = sqlite3.Row
    return conn
