"""Tests for CLI diagnostics commands."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from mem0ry.cli.diagnostics import doctor, version


def _fresh_diagnostics(monkeypatch: pytest.MonkeyPatch, **env: str):
    """Reload diagnostics so MemoryConfig picks up env changes."""
    from mem0ry import config as config_module

    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(config_module)

    from mem0ry import cli

    return importlib.reload(cli.diagnostics)


def test_version_prints_installed_version(capsys: pytest.CaptureFixture[str]) -> None:
    version()
    captured = capsys.readouterr()
    assert "mymem0ry" in captured.out


def test_version_handles_missing_package(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("mem0ry.cli.diagnostics.pkg_version", side_effect=Exception("boom")):
        version()
    captured = capsys.readouterr()
    assert "unknown version" in captured.out


def test_stats_no_database(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diag = _fresh_diagnostics(monkeypatch, DB_PATH=str(tmp_path / "missing.db"))
    with pytest.raises(typer.Exit):
        diag.stats()
    captured = capsys.readouterr()
    assert "Database not found" in captured.out


def test_stats_shows_counts(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "memories.db"
    db_path.write_text("")  # simulate existing database file
    diag = _fresh_diagnostics(monkeypatch, DB_PATH=str(db_path))
    mock_result = {
        "total": 42,
        "by_scope": [{"scope": "global", "count": 40}, {"scope": "project", "count": 2}],
        "by_type": [{"memory_type": "fact", "count": 10}],
        "by_source": [{"source": "manual", "count": 42}],
        "projects": [{"project_id": "github.com/x/y", "count": 2}],
    }

    with patch("mem0ry.db.store.stats", return_value=mock_result):
        diag.stats()

    captured = capsys.readouterr()
    assert "Total memories: 42" in captured.out
    assert "global: 40" in captured.out
    assert "fact: 10" in captured.out


def test_projects_no_database(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diag = _fresh_diagnostics(monkeypatch, DB_PATH=str(tmp_path / "missing.db"))
    with pytest.raises(typer.Exit):
        diag.projects()
    captured = capsys.readouterr()
    assert "Database not found" in captured.out


def test_projects_lists_rows(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "memories.db"
    db_path.write_text("")  # simulate existing database file
    diag = _fresh_diagnostics(monkeypatch, DB_PATH=str(db_path))
    result = [{"project_id": "github.com/x/y", "project_path": "/x/y", "count": 5}]

    with patch("mem0ry.db.store.list_projects", return_value=result):
        diag.projects()

    captured = capsys.readouterr()
    assert "github.com/x/y" in captured.out
    assert "5" in captured.out


def test_doctor_all_ok(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "memories.db"))
    monkeypatch.setenv("SPACY_MODEL", "pt_core_news_lg")

    with (
        patch("mem0ry.cli.diagnostics._check_spacy") as check_spacy,
        patch("mem0ry.cli.diagnostics._check_doltlite") as check_doltlite,
        patch("mem0ry.cli.diagnostics._check_db") as check_db,
        patch("mem0ry.cli.diagnostics._check_index") as check_index,
    ):
        doctor()

    captured = capsys.readouterr()
    assert "tudo OK" in captured.out
    check_spacy.assert_called_once()
    check_doltlite.assert_called_once()
    check_db.assert_called_once()
    assert check_index.call_count == 3


def test_doctor_with_failing_checks(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "memories.db"))
    monkeypatch.setenv("SPACY_MODEL", "pt_core_news_lg")

    def failing_check(config, ok, fail):
        fail("spacy missing")

    with (
        patch("mem0ry.cli.diagnostics._check_spacy", side_effect=failing_check),
        patch("mem0ry.cli.diagnostics._check_db"),
        patch("mem0ry.cli.diagnostics._check_index"),
    ):
        with pytest.raises(typer.Exit):
            doctor()

    captured = capsys.readouterr()
    assert "1 erro" in captured.out


def test_check_db_warns_when_missing(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mem0ry.cli.diagnostics import _check_db

    config = MagicMock()
    config.db_path = str(tmp_path / "missing.db")
    _check_db(config, lambda m: None, lambda m: capsys.readouterr(), lambda m: None)
    # Just ensure no exception; the warn callback prints to stdout.


def test_check_db_ok_when_exists(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    from mem0ry.cli.diagnostics import _check_db

    db_path = tmp_path / "memories.db"
    # Create a minimal DB with schema_meta so init_schema works.
    from mem0ry.db.connection import get_connection
    from mem0ry.db.schema import init_schema

    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()

    config = MagicMock()
    config.db_path = str(db_path)
    ok_messages: list[str] = []
    _check_db(config, ok_messages.append, lambda m: None, lambda m: None)
    assert any("schema v" in msg for msg in ok_messages)


def test_check_spacy_installed(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from mem0ry.cli.diagnostics import _check_spacy

    class FakeConfig:
        spacy_model = "pt_core_news_lg"

    ok_messages: list[str] = []
    fail_messages: list[str] = []
    with patch("spacy.util.get_installed_models", return_value=["pt_core_news_lg"]):
        _check_spacy(FakeConfig(), ok_messages.append, fail_messages.append)
    assert any("pt_core_news_lg instalado" in msg for msg in ok_messages)
    assert not fail_messages


def test_check_spacy_downloads_missing(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from mem0ry.cli.diagnostics import _check_spacy

    class FakeConfig:
        spacy_model = "pt_core_news_lg"

    ok_messages: list[str] = []
    fail_messages: list[str] = []
    with (
        patch("spacy.util.get_installed_models", return_value=[]),
        patch("mem0ry.cli.diagnostics._download_spacy_model") as download,
    ):
        _check_spacy(FakeConfig(), ok_messages.append, fail_messages.append)
    download.assert_called_once_with("pt_core_news_lg")
    assert not fail_messages


def test_check_spacy_import_error(capsys: pytest.CaptureFixture[str]) -> None:
    from mem0ry.cli.diagnostics import _check_spacy

    class FakeConfig:
        spacy_model = "pt_core_news_lg"

    fail_messages: list[str] = []
    with patch("builtins.__import__", side_effect=ImportError("no spacy")):
        _check_spacy(FakeConfig(), lambda m: None, fail_messages.append)
    assert any("spacy nao instalado" in msg for msg in fail_messages)
