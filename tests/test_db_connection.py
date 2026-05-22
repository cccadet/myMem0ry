"""Tests for db.connection — SQLite connection factory."""

from __future__ import annotations

from pathlib import Path

from mem0ry.db.connection import get_connection


def test_get_connection_creates_file(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    conn = get_connection(db)
    assert db.exists()
    conn.close()


def test_get_connection_creates_parent_dirs(tmp_path: Path) -> None:
    db = tmp_path / "sub" / "dir" / "test.db"
    conn = get_connection(db)
    assert db.exists()
    conn.close()


def test_get_connection_wal_mode(tmp_path: Path) -> None:
    db = tmp_path / "wal.db"
    conn = get_connection(db)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_get_connection_row_factory(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "row.db"
    conn = get_connection(db)
    assert conn.row_factory is sqlite3.Row
    conn.close()
