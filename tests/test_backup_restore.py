"""Tests for backup and restore CLI commands."""

from __future__ import annotations

import tarfile
from pathlib import Path

from typer.testing import CliRunner

from mem0ry.cli.main import app

runner = CliRunner()


def test_backup_nothing(tmp_path: Path) -> None:
    import mem0ry.cli.main as mod
    from unittest.mock import patch

    with patch.object(
        mod, "MemoryConfig"
    ) as MockConfig:
        cfg = MockConfig.return_value
        cfg.db_path = str(tmp_path / "missing.db")
        cfg.conversations_dir = str(tmp_path / "missing_conv")

        result = runner.invoke(app, ["backup", "--to", str(tmp_path / "out.tar.gz")])
    assert result.exit_code != 0
    assert "Nothing to backup" in result.output


def test_backup_creates_tarball(tmp_path: Path) -> None:
    import mem0ry.cli.main as mod
    from mem0ry.db.connection import get_connection
    from mem0ry.db.schema import init_schema
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()

    dest = tmp_path / "backup.tar.gz"

    with patch.object(mod, "MemoryConfig") as MockConfig:
        cfg = MockConfig.return_value
        cfg.db_path = str(db_path)
        cfg.conversations_dir = str(tmp_path / "missing_conv")

        result = runner.invoke(app, ["backup", "--to", str(dest)])

    assert result.exit_code == 0
    assert dest.exists()
    assert "Backup saved" in result.output


def test_restore_from_tarball(tmp_path: Path) -> None:
    import mem0ry.cli.main as mod
    from unittest.mock import patch

    src_dir = tmp_path / "source"
    src_dir.mkdir()
    db_file = src_dir / "test.db"
    db_file.write_text("fake db content", encoding="utf-8")

    tarball = tmp_path / "backup.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(db_file, arcname="test.db")

    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()

    with patch.object(mod, "MemoryConfig") as MockConfig:
        cfg = MockConfig.return_value
        cfg.db_path = str(restore_dir / "test.db")

        result = runner.invoke(app, ["restore", "--from", str(tarball)])

    assert result.exit_code == 0
    assert "Restored" in result.output


def test_restore_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["restore", "--from", str(tmp_path / "nonexistent.tar.gz")]
    )
    assert result.exit_code != 0
    assert "not found" in result.output
