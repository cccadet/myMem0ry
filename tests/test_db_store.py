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
    create_memory(db, content="global fact", scope="global", title="G1", memory_type="fact")
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
    create_memory(db, content="global only", scope="global", title="G1", memory_type="fact")
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


def test_search_memories_by_query_text(db: Path) -> None:
    create_memory(db, content="how to configure the auth token", scope="global", title="A")
    create_memory(db, content="database connection pooling tips", scope="global", title="B")

    results = search_memories(db, query="auth token")
    assert len(results) == 1
    assert results[0]["title"] == "A"


def test_search_memories_excludes_deleted(db: Path) -> None:
    from mem0ry.db.store import delete_memory

    mem_id = create_memory(db, content="soon gone", scope="global", title="Gone")
    create_memory(db, content="stays here", scope="global", title="Stay")
    delete_memory(db, mem_id)

    results = search_memories(db, scope="global")
    titles = {r["title"] for r in results}
    assert "Gone" not in titles
    assert "Stay" in titles


def test_get_memory_by_id(db: Path) -> None:
    from mem0ry.db.store import get_memory_by_id

    mem_id = create_memory(db, content="find me", scope="global", title="Findable")
    mem = get_memory_by_id(db, mem_id)
    assert mem is not None
    assert mem["content"] == "find me"
    assert get_memory_by_id(db, "nonexistent") is None


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


def test_forget_sweep_purges_md_on_hard_delete(db: Path, tmp_path: Path) -> None:
    from mem0ry.db.retention import forget_sweep

    memories_dir = tmp_path / "memories"
    rel = "2026-05-29/deadbeef0001.md"
    md_file = memories_dir / rel
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("# Old\n> id: deadbeef0001\n\nstale", encoding="utf-8")

    mem_id = create_memory(
        db, content="stale", scope="global", memory_type="log",
        title="Old", file_path=rel,
    )

    # Soft-deleted with an already-expired grace → eligible for hard delete.
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn = get_connection(db)
    conn.execute(
        "UPDATE memories SET deleted_at = ?, grace_until = ? WHERE id = ?",
        (past, past, mem_id),
    )
    conn.commit()
    conn.close()

    result = forget_sweep(db, dry_run=False, memories_dir=memories_dir)

    assert mem_id in result["hard_deleted"]
    assert result["files_removed_count"] == 1
    assert rel in result["files_removed"]
    assert not md_file.exists()


def test_forget_sweep_keeps_md_during_grace(db: Path, tmp_path: Path) -> None:
    """Soft-deleted but still inside the grace window → the .md must survive."""
    from mem0ry.db.retention import forget_sweep

    memories_dir = tmp_path / "memories"
    rel = "2026-05-29/cafe00000002.md"
    md_file = memories_dir / rel
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("# Keep\n", encoding="utf-8")

    mem_id = create_memory(
        db, content="keep", scope="global", memory_type="log",
        title="Keep", file_path=rel,
    )

    now = datetime.now(timezone.utc)
    deleted = (now - timedelta(days=1)).isoformat()
    future_grace = (now + timedelta(days=6)).isoformat()
    conn = get_connection(db)
    conn.execute(
        "UPDATE memories SET deleted_at = ?, grace_until = ? WHERE id = ?",
        (deleted, future_grace, mem_id),
    )
    conn.commit()
    conn.close()

    result = forget_sweep(db, dry_run=False, memories_dir=memories_dir)

    assert mem_id not in result["hard_deleted"]
    assert result["files_removed_count"] == 0
    assert md_file.exists()


def test_get_context_excludes_superseded(db: Path) -> None:
    from mem0ry.db.store import evolve_memories

    old = create_memory(db, content="superseded fact", scope="global", memory_type="fact", title="Old")
    evolve_memories(db, old_ids=[old], evolved_content="new fact", rationale="test")

    ctx = get_context(db, top_k=10)
    assert all(r["id"] != old for r in ctx)


def test_search_excludes_superseded(db: Path) -> None:
    from mem0ry.db.store import evolve_memories

    old = create_memory(db, content="superseded searchable", scope="global", memory_type="fact", title="OldSearch")
    evolve_memories(db, old_ids=[old], evolved_content="new fact", rationale="test")

    results = search_memories(db, query="superseded")
    assert all(r["id"] != old for r in results)


def test_fts5_table_created(db: Path) -> None:
    conn = get_connection(db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "memories_fts" in tables


def test_fts5_ranking(db: Path) -> None:
    create_memory(db, content="authentication token JWT bearer", scope="global", title="Auth")
    create_memory(db, content="token is a small word that appears briefly", scope="global", title="Brief")
    create_memory(db, content="unrelated content about database", scope="global", title="DB")

    results = search_memories(db, query="authentication token")
    assert len(results) >= 2
    assert results[0]["title"] == "Auth"


def test_fts5_or_match(db: Path) -> None:
    create_memory(db, content="only about authentication", scope="global", title="AuthOnly")
    create_memory(db, content="only about database", scope="global", title="DBOnly")

    results = search_memories(db, query="authentication database")
    titles = {r["title"] for r in results}
    assert "AuthOnly" in titles
    assert "DBOnly" in titles


def test_fts5_sync_on_insert(db: Path) -> None:
    create_memory(db, content="findable via fts", scope="global", title="FTS")
    results = search_memories(db, query="findable")
    assert len(results) == 1
    assert results[0]["title"] == "FTS"


def test_fts5_sync_on_soft_delete(db: Path) -> None:
    from mem0ry.db.store import delete_memory

    mem_id = create_memory(db, content="temporary fts content", scope="global", title="Temp")
    assert len(search_memories(db, query="temporary")) == 1

    delete_memory(db, mem_id)
    assert len(search_memories(db, query="temporary")) == 0


def test_fts5_sync_on_restore(db: Path) -> None:
    from mem0ry.db.store import delete_memory, restore_memory

    mem_id = create_memory(db, content="restored fts content", scope="global", title="Restore")
    delete_memory(db, mem_id)
    assert len(search_memories(db, query="restored")) == 0

    restore_memory(db, mem_id)
    assert len(search_memories(db, query="restored")) == 1


def test_fts5_sync_on_update(db: Path) -> None:
    from mem0ry.db.store import update_memory

    mem_id = create_memory(db, content="original content", scope="global", title="Update")
    assert len(search_memories(db, query="original")) == 1
    assert len(search_memories(db, query="modified")) == 0

    update_memory(db, mem_id, content="modified content")
    assert len(search_memories(db, query="modified")) == 1
    assert len(search_memories(db, query="original")) == 0


def test_fts5_accent_insensitive(db: Path) -> None:
    create_memory(db, content="configuração do sistema de autenticação", scope="global", title="Config")
    results = search_memories(db, query="configuracao")
    assert len(results) == 1


def test_fts5_superseded_excluded(db: Path) -> None:
    from mem0ry.db.store import evolve_memories

    old = create_memory(db, content="deprecated approach for caching", scope="global", memory_type="fact", title="Old")
    evolve_memories(db, old_ids=[old], evolved_content="new caching approach", rationale="improved")

    results = search_memories(db, query="deprecated caching")
    assert all(r["id"] != old for r in results)


def test_search_expanded_terms(db: Path) -> None:
    create_memory(db, content="login page with credentials", scope="global", title="Login")
    create_memory(db, content="unrelated topic", scope="global", title="Other")

    results = search_memories(db, query="xyznonexistent", expanded_terms=["credentials"])
    assert len(results) == 1
    assert results[0]["title"] == "Login"


def test_search_no_query_returns_all(db: Path) -> None:
    create_memory(db, content="alpha", scope="global", title="A")
    create_memory(db, content="beta", scope="global", title="B")

    results = search_memories(db)
    assert len(results) == 2


def test_normalize_strips_accents() -> None:
    from mem0ry.db.store_memories import _normalize

    assert _normalize("configuração") == "configuracao"
    assert _normalize("autenticação") == "autenticacao"
    assert _normalize("São Paulo") == "sao paulo"


def test_strip_accents() -> None:
    from mem0ry.db.store_memories import _strip_accents

    assert _strip_accents("índice") == "indice"
    assert _strip_accents("CONFIANÇA") == "CONFIANCA"
    assert _strip_accents("hello") == "hello"


def test_query_terms_normalizes() -> None:
    from mem0ry.db.store_memories import _query_terms

    terms = _query_terms("configuração do sistema")
    assert "configuracao" in terms
    assert "sistema" in terms
    assert "do" not in terms


def test_query_terms_filters_stop_words() -> None:
    from mem0ry.db.store_memories import _query_terms

    terms = _query_terms("the authentication and the authorization")
    assert "authentication" in terms
    assert "authorization" in terms
    assert "the" not in terms
    assert "and" not in terms


def test_query_terms_raw_preserves_accents() -> None:
    from mem0ry.db.store_memories import _query_terms_raw

    terms = _query_terms_raw("configuração do sistema")
    assert "configuração" in terms
    assert "sistema" in terms
    assert "do" not in terms
