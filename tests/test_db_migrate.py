"""Tests for db.migrate — migration from .md files to structured database."""

from __future__ import annotations

from pathlib import Path

from mem0ry.db.connection import get_connection
from mem0ry.db.migrate import migrate_v1_to_v2, migrate_v2_to_v3


def _write_md(conv_dir: Path, date_str: str, title: str, mem_id: str) -> Path:
    d = conv_dir / date_str
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{title}.md"
    p.write_text(
        f"# {title}\n> id: {mem_id} | date: {date_str}\n\nSome content here.\n",
        encoding="utf-8",
    )
    return p


def test_migrate_empty_dir(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    db_path = tmp_path / "memories.db"

    result = migrate_v1_to_v2(conv_dir, db_path)
    assert result["total"] == 0
    assert result["migrated"] == 0


def test_migrate_md_files(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    _write_md(conv_dir, "2025-01-15", "Test Chat", "abc123")
    _write_md(conv_dir, "2025-01-16", "Another", "def456")

    result = migrate_v1_to_v2(conv_dir, db_path)
    assert result["total"] == 2
    assert result["migrated"] == 2
    assert result["skipped"] == 0


def test_migrate_skips_already_migrated(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    _write_md(conv_dir, "2025-01-15", "Test", "abc")

    migrate_v1_to_v2(conv_dir, db_path)
    result = migrate_v1_to_v2(conv_dir, db_path)
    assert result["skipped"] == 1
    assert result["migrated"] == 0


def test_migrate_skips_non_md_files(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    d = conv_dir / "2025-01-15"
    d.mkdir(parents=True)
    (d / "data.json").write_text("{}", encoding="utf-8")

    result = migrate_v1_to_v2(conv_dir, db_path)
    assert result["total"] == 0
    assert result["migrated"] == 0


def test_migrate_nonexistent_dir(tmp_path: Path) -> None:
    result = migrate_v1_to_v2(tmp_path / "missing", tmp_path / "db")
    assert result["total"] == 0


def test_migrate_creates_db(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    _write_md(conv_dir, "2025-01-15", "Test", "abc")
    migrate_v1_to_v2(conv_dir, db_path)

    assert db_path.exists()
    conn = get_connection(db_path)
    count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
    conn.close()
    assert count == 1


def test_migrate_v2_to_v3_drops_and_reingests(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    _write_md(conv_dir, "2025-01-15", "Test Chat", "abc123")
    _write_md(conv_dir, "2025-01-16", "Architecture Decision", "def456")

    migrate_v1_to_v2(conv_dir, db_path)

    result = migrate_v2_to_v3(conv_dir, db_path)
    assert result["total"] == 2
    assert result["migrated"] == 2
    assert result["skipped"] == 0

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT memory_type, title FROM memories ORDER BY title"
    ).fetchall()
    conn.close()
    types = {row["title"]: row["memory_type"] for row in rows}
    assert types["Test Chat"] == "log"
    assert types["Architecture Decision"] == "decision"


def test_migrate_v2_to_v3_empty_dir(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    db_path = tmp_path / "memories.db"

    result = migrate_v2_to_v3(conv_dir, db_path)
    assert result["total"] == 0
    assert result["migrated"] == 0


def test_migrate_v2_to_v3_skips_non_md(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    d = conv_dir / "2025-01-15"
    d.mkdir(parents=True)
    (d / "data.json").write_text("{}", encoding="utf-8")

    result = migrate_v2_to_v3(conv_dir, db_path)
    assert result["total"] == 0
    assert result["migrated"] == 0
    assert result["skipped"] == 0


def test_migrate_v2_to_v3_guesses_fact(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    db_path = tmp_path / "memories.db"

    _write_md(conv_dir, "2025-01-15", "Stack preference note", "abc")

    migrate_v2_to_v3(conv_dir, db_path)

    conn = get_connection(db_path)
    row = conn.execute("SELECT memory_type FROM memories").fetchone()
    conn.close()
    assert row["memory_type"] == "fact"
