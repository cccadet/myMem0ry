"""SQLite connection factory for the memories database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec  # type: ignore[import-untyped]


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with sqlite-vec extension loaded.

    Creates parent directories if needed. The connection uses
    WAL journal mode for concurrent read/write support.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    return conn
