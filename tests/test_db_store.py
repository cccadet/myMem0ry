"""Tests for db.store — CRUD operations on the memories database (v3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import (
    create_memory,
    end_session,
    get_context,
    list_projects,
    list_scopes,
    search_memories,
    stats,
    touch_memory,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_create_memory_returns_id(db: Path) -> None:
    mem_id = create_memory(db, content="test", scope="global", title="Test")
    assert len(mem_id) == 12


def test_create_memory_invalid_scope(db: Path) -> None:
    with pytest.raises(ValueError, match="Invalid scope"):
        create_memory(db, content="test", scope="invalid")


def test_create_memory_invalid_source(db: Path) -> None:
    with pytest.raises(ValueError, match="Invalid source"):
        create_memory(db, content="test", source="bad")


def test_create_memory_invalid_memory_type(db: Path) -> None:
    with pytest.raises(ValueError, match="Invalid memory_type"):
        create_memory(db, content="test", memory_type="unknown")


def test_create_memory_persists(db: Path) -> None:
    create_memory(db, content="persisted", scope="global", title="P")
    conn = get_connection(db)
    row = conn.execute("SELECT content FROM memories WHERE scope='global'").fetchone()
    conn.close()
    assert row["content"] == "persisted"


def test_create_memory_project_scope(db: Path) -> None:
    create_memory(
        db,
        content="project note",
        scope="project",
        project_id="github.com/user/repo",
        project_path="/home/user/repo",
        title="PN",
    )
    conn = get_connection(db)
    row = conn.execute(
        "SELECT project_id, project_path FROM memories WHERE scope='project'"
    ).fetchone()
    conn.close()
    assert row["project_id"] == "github.com/user/repo"
    assert row["project_path"] == "/home/user/repo"


def test_create_memory_with_context(db: Path) -> None:
    create_memory(
        db,
        content="branch note",
        scope="context",
        project_id="github.com/user/repo",
        context="feat/auth",
        title="BN",
    )
    conn = get_connection(db)
    row = conn.execute(
        "SELECT context, scope FROM memories WHERE scope='context'"
    ).fetchone()
    conn.close()
    assert row["context"] == "feat/auth"


def test_create_memory_with_type(db: Path) -> None:
    create_memory(db, content="a fact", scope="global", memory_type="fact", title="F")
    conn = get_connection(db)
    row = conn.execute("SELECT memory_type FROM memories WHERE title='F'").fetchone()
    conn.close()
    assert row["memory_type"] == "fact"


def test_get_context_empty(db: Path) -> None:
    result = get_context(db)
    assert result == []


def test_get_context_cascata(db: Path) -> None:
    create_memory(db, content="global fact", scope="global", title="G1")
    create_memory(
        db,
        content="project fact",
        scope="project",
        project_id="github.com/x/y",
        title="P1",
    )
    create_memory(
        db,
        content="context fact",
        scope="context",
        project_id="github.com/x/y",
        context="main",
        title="C1",
    )
    create_memory(
        db,
        content="session fact",
        scope="session",
        session_id="s1",
        title="S1",
    )

    result = get_context(
        db,
        project_id="github.com/x/y",
        context="main",
        session_id="s1",
        top_k=10,
    )
    scopes = {r["scope"] for r in result}
    assert "session" in scopes
    assert "context" in scopes
    assert "project" in scopes
    assert "global" in scopes


def test_get_context_only_global(db: Path) -> None:
    create_memory(db, content="global only", scope="global", title="G1")
    result = get_context(db, top_k=5)
    assert len(result) == 1
    assert result[0]["scope"] == "global"


def test_list_scopes(db: Path) -> None:
    create_memory(db, content="g1", scope="global", title="G1")
    create_memory(db, content="g2", scope="global", title="G2")
    create_memory(
        db,
        content="p1",
        scope="project",
        project_id="github.com/x/y",
        title="P1",
    )

    result = list_scopes(db)
    scope_map = {r["scope"]: r["count"] for r in result}
    assert scope_map["global"] == 2
    assert scope_map["project"] == 1


def test_stats(db: Path) -> None:
    create_memory(
        db, content="g", scope="global", source="manual", memory_type="fact", title="G"
    )
    create_memory(
        db,
        content="p",
        scope="project",
        source="import",
        project_id="github.com/x/y",
        memory_type="decision",
        title="P",
    )

    result = stats(db)
    assert result["total"] == 2
    assert len(result["by_scope"]) == 2
    assert len(result["by_source"]) == 2
    assert len(result["by_type"]) == 2
    assert len(result["projects"]) == 1


def test_end_session(db: Path) -> None:
    create_memory(db, content="s", scope="session", session_id="abc", title="S")
    found = end_session(db, "abc", summary="Done")
    assert found is True


def test_end_session_not_found(db: Path) -> None:
    found = end_session(db, "nonexistent")
    assert found is False


def test_end_session_with_summary(db: Path) -> None:
    create_memory(db, content="s", scope="session", session_id="xyz", title="S")
    end_session(db, "xyz", summary="Completed task")

    conn = get_connection(db)
    rows = conn.execute("SELECT title FROM memories WHERE session_id='xyz'").fetchall()
    conn.close()
    titles = [r["title"] for r in rows]
    assert any("summary" in t.lower() for t in titles)


def test_search_memories_by_scope(db: Path) -> None:
    create_memory(db, content="global", scope="global", title="G")
    create_memory(
        db,
        content="project",
        scope="project",
        project_id="github.com/x/y",
        title="P",
    )

    results = search_memories(db, scope="global")
    assert len(results) == 1
    assert results[0]["scope"] == "global"


def test_search_memories_by_project_id(db: Path) -> None:
    create_memory(db, content="global", scope="global", title="G")
    create_memory(
        db,
        content="project",
        scope="project",
        project_id="github.com/x/y",
        title="P",
    )

    results = search_memories(db, project_id="github.com/x/y")
    assert len(results) == 2


def test_search_memories_by_memory_type(db: Path) -> None:
    create_memory(db, content="a fact", scope="global", memory_type="fact", title="F")
    create_memory(db, content="a log", scope="global", memory_type="log", title="L")

    results = search_memories(db, memory_type="fact")
    assert len(results) == 1
    assert results[0]["memory_type"] == "fact"


def test_search_memories_by_context(db: Path) -> None:
    create_memory(
        db,
        content="ctx note",
        scope="context",
        project_id="github.com/x/y",
        context="feat/auth",
        title="C",
    )
    create_memory(db, content="global note", scope="global", title="G")

    results = search_memories(db, context="feat/auth")
    assert len(results) == 2


def test_list_projects(db: Path) -> None:
    create_memory(
        db,
        content="a",
        scope="project",
        project_id="github.com/x/p1",
        project_path="/p1",
        title="A",
    )
    create_memory(
        db,
        content="b",
        scope="project",
        project_id="github.com/x/p2",
        project_path="/p2",
        title="B",
    )
    create_memory(
        db,
        content="c",
        scope="project",
        project_id="github.com/x/p1",
        project_path="/p1",
        title="C",
    )

    result = list_projects(db)
    assert len(result) == 2
    proj1 = next(r for r in result if r["project_id"] == "github.com/x/p1")
    assert proj1["count"] == 2


def test_list_projects_empty(db: Path) -> None:
    result = list_projects(db)
    assert result == []


def test_touch_memory(db: Path) -> None:
    mem_id = create_memory(db, content="touch me", scope="global", title="T")
    found = touch_memory(db, mem_id)
    assert found is True

    conn = get_connection(db)
    row = conn.execute(
        "SELECT access_count, last_accessed_at FROM memories WHERE id = ?", (mem_id,)
    ).fetchone()
    conn.close()
    assert row["access_count"] == 1
    assert row["last_accessed_at"] is not None


def test_touch_memory_not_found(db: Path) -> None:
    found = touch_memory(db, "nonexistent")
    assert found is False


def test_decay_memories_dry_run(db: Path) -> None:
    from mem0ry.db.retention import forget_sweep

    create_memory(
        db,
        content="old session",
        scope="session",
        session_id="old",
        memory_type="log",
        title="Old",
    )

    past = (
        datetime.now(timezone.utc) - timedelta(days=200)
    ).isoformat()
    conn = get_connection(db)
    conn.execute("UPDATE memories SET created_at = ? WHERE title = 'Old'", (past,))
    conn.commit()
    conn.close()

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 1

    conn = get_connection(db)
    count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
    conn.close()
    assert count == 1


def test_decay_memories_deletes(db: Path) -> None:
    from datetime import timedelta

    create_memory(
        db,
        content="old session",
        scope="session",
        session_id="old",
        memory_type="log",
        title="Old",
    )
    create_memory(
        db, content="a fact", scope="global", memory_type="fact", title="Fact"
    )

    past = (
        datetime.now(timezone.utc) - timedelta(days=200)
    ).isoformat()
    conn = get_connection(db)
    conn.execute("UPDATE memories SET created_at = ? WHERE title = 'Old'", (past,))
    conn.commit()
    conn.close()

    from mem0ry.db.retention import forget_sweep

    result = forget_sweep(db, dry_run=False)
    assert result["soft_count"] == 1

    conn = get_connection(db)
    count = conn.execute(
        "SELECT count(*) FROM memories WHERE deleted_at IS NULL"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_decay_preserves_non_session_logs(db: Path) -> None:
    create_memory(
        db, content="project log", scope="project", memory_type="log", title="PL"
    )

    from mem0ry.db.retention import forget_sweep

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 0
