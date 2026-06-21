"""Tests for db.connection — SQLite/DoltLite detection and fallback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mem0ry.db.connection import get_connection, is_doltlite_db
from mem0ry.db.schema import init_schema


def test_get_connection_creates_plain_sqlite_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "memories.db"
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        assert is_doltlite_db(conn) is False
        version = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        assert version["value"] == "9"
    finally:
        conn.close()


def test_is_doltlite_db_returns_false_for_plain_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "plain.db"
    conn = get_connection(db_path)
    try:
        assert is_doltlite_db(conn) is False
    finally:
        conn.close()


def test_doltlite_unavailable_falls_back_to_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "fallback.db"
    with patch("mem0ry.db.connection._is_doltlite_available", return_value=False):
        conn = get_connection(db_path)
        try:
            init_schema(conn)
            assert is_doltlite_db(conn) is False
        finally:
            conn.close()


def test_existing_plain_sqlite_kept_when_doltlite_available(tmp_path: Path) -> None:
    db_path = tmp_path / "existing.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()

    with patch("mem0ry.db.connection._is_doltlite_available", return_value=True):
        conn = get_connection(db_path)
        try:
            assert is_doltlite_db(conn) is False
        finally:
            conn.close()


def test_get_connection_loads_sqlite_vec(tmp_path: Path) -> None:
    db_path = tmp_path / "vec.db"
    conn = get_connection(db_path)
    try:
        version = conn.execute("SELECT vec_version()").fetchone()
        assert version[0]
    finally:
        conn.close()
