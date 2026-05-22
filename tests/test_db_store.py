"""Tests for db.store — CRUD operations on the memories database."""

from __future__ import annotations

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


def test_create_memory_persists(db: Path) -> None:
    create_memory(db, content="persisted", scope="global", title="P")
    conn = get_connection(db)
    row = conn.execute("SELECT content FROM memories WHERE scope='global'").fetchone()
    conn.close()
    assert row["content"] == "persisted"


def test_create_memory_project_scope(db: Path) -> None:
    create_memory(
        db, content="project note", scope="project",
        project_path="/home/user/proj", title="PN",
    )
    conn = get_connection(db)
    row = conn.execute("SELECT project_path FROM memories WHERE scope='project'").fetchone()
    conn.close()
    assert row["project_path"] == "/home/user/proj"


def test_get_context_empty(db: Path) -> None:
    result = get_context(db)
    assert result == []


def test_get_context_aggregates_scopes(db: Path) -> None:
    create_memory(db, content="global item", scope="global", title="G1")
    create_memory(db, content="project item", scope="project", project_path="/p", title="P1")
    create_memory(db, content="session item", scope="session", session_id="s1", title="S1")

    result = get_context(db, project_path="/p", top_k=5)
    scopes = {r["scope"] for r in result}
    assert "session" in scopes
    assert "project" in scopes
    assert "global" in scopes


def test_list_scopes(db: Path) -> None:
    create_memory(db, content="g1", scope="global", title="G1")
    create_memory(db, content="g2", scope="global", title="G2")
    create_memory(db, content="p1", scope="project", project_path="/p", title="P1")

    result = list_scopes(db)
    scope_map = {r["scope"]: r["count"] for r in result}
    assert scope_map["global"] == 2
    assert scope_map["project"] == 1


def test_stats(db: Path) -> None:
    create_memory(db, content="g", scope="global", source="manual", title="G")
    create_memory(db, content="p", scope="project", source="import", project_path="/x", title="P")

    result = stats(db)
    assert result["total"] == 2
    assert len(result["by_scope"]) == 2
    assert len(result["by_source"]) == 2
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
    create_memory(db, content="project", scope="project", project_path="/p", title="P")

    results = search_memories(db, scope="global")
    assert len(results) == 1
    assert results[0]["scope"] == "global"


def test_search_memories_by_project(db: Path) -> None:
    create_memory(db, content="global", scope="global", title="G")
    create_memory(db, content="project", scope="project", project_path="/p", title="P")

    results = search_memories(db, project_path="/p")
    assert len(results) == 2


def test_list_projects(db: Path) -> None:
    create_memory(db, content="a", scope="project", project_path="/proj1", title="A")
    create_memory(db, content="b", scope="project", project_path="/proj2", title="B")
    create_memory(db, content="c", scope="project", project_path="/proj1", title="C")

    result = list_projects(db)
    assert len(result) == 2
    proj1 = next(r for r in result if r["path"] == "/proj1")
    assert proj1["count"] == 2


def test_list_projects_empty(db: Path) -> None:
    result = list_projects(db)
    assert result == []
