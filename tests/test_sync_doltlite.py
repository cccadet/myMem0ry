"""Tests for DoltLite sync helpers and CLI (SQLite fallback paths)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from mem0ry.cli.main import app
from mem0ry.db.connection import get_connection
from mem0ry.db.doltlite_sync import auto_commit, dolt_pull, dolt_push, dolt_status
from mem0ry.db.schema import init_schema

runner = CliRunner()


def test_auto_commit_noop_on_plain_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        assert auto_commit(conn) is None
    finally:
        conn.close()


def test_dolt_push_pull_noop_on_plain_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        assert dolt_push(conn) is None
        assert dolt_pull(conn) is None
    finally:
        conn.close()


def test_dolt_status_on_plain_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        status = dolt_status(conn)
        assert status["engine"] == "sqlite"
        assert status["clean"] is True
    finally:
        conn.close()


def test_sync_status_shows_sqlite_for_plain_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "memories.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()

    result = runner.invoke(app, ["sync", "status"])
    assert result.exit_code == 0
    assert "plain SQLite" in result.output or "SQLite" in result.output


def test_sync_init_fails_when_doltlite_unavailable(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "memories.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with patch("mem0ry.db.connection._is_doltlite_available", return_value=False):
        result = runner.invoke(app, ["sync", "init"])
        assert result.exit_code == 1
        assert "Failed" in result.output or "plain SQLite" in result.output


def test_sync_push_fails_on_plain_sqlite(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "memories.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()

    result = runner.invoke(app, ["sync", "push"])
    assert result.exit_code == 1
    assert "only available for DoltLite" in result.output


def test_sync_pull_fails_on_plain_sqlite(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "memories.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()

    result = runner.invoke(app, ["sync", "pull"])
    assert result.exit_code == 1
    assert "only available for DoltLite" in result.output
