"""Tests for the web UI module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import create_memory
from mem0ry.web import get_web_routes

from starlette.applications import Starlette


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    """Patch _db_path in every web.pages submodule that imported it."""
    import importlib

    def target():
        return db_path

    for name in (
        "audit", "dashboard", "handoffs", "import_export",
        "memories", "observations", "projects", "search", "trash",
    ):
        mod = importlib.import_module(f"mem0ry.web.pages.{name}")
        if hasattr(mod, "_db_path"):
            monkeypatch.setattr(mod, "_db_path", target)
    monkeypatch.setattr("mem0ry.web.templates._db_path", target)


@pytest.fixture
def client(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _patch_db_path(monkeypatch, tmp_db)
    app = Starlette(routes=get_web_routes())
    c = TestClient(app)
    # The UI defaults to Portuguese; pin the test client to English so the
    # assertions below can stay language-stable. PT default is covered separately.
    c.cookies.set("lang", "en")
    return c


def _seed(db_path: Path) -> list[str]:
    ids = []
    ids.append(create_memory(
        db_path, content="Test fact about Python", scope="global",
        memory_type="fact", title="Python fact", source="manual",
    ))
    ids.append(create_memory(
        db_path, content="Decision: use SQLite", scope="project",
        project_id="github.com/test/repo", memory_type="decision",
        title="DB decision", source="opencode",
    ))
    ids.append(create_memory(
        db_path, content="Pattern: early returns", scope="context",
        project_id="github.com/test/repo", context="main",
        memory_type="pattern", title="Code pattern", source="claude-code",
    ))
    return ids


def test_dashboard_no_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_db_path(monkeypatch, tmp_path / "missing.db")
    app = Starlette(routes=get_web_routes())
    c = TestClient(app)
    c.cookies.set("lang", "en")
    resp = c.get("/")
    assert resp.status_code == 200
    assert "No database found" in resp.text


def test_default_language_is_portuguese(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_db_path(monkeypatch, tmp_db)
    app = Starlette(routes=get_web_routes())
    c = TestClient(app)  # no lang cookie -> default pt
    resp = c.get("/")
    assert resp.status_code == 200
    assert 'lang="pt"' in resp.text
    assert "Painel" in resp.text  # nav "Dashboard" in PT


def test_dashboard_with_data(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "myMem0ry" in resp.text
    assert "Python fact" in resp.text
    assert "3" in resp.text


def test_projects_page(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert "github.com/test/repo" in resp.text


def test_project_detail(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/project/github.com/test/repo")
    assert resp.status_code == 200
    assert "DB decision" in resp.text


def test_project_global(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/project/global")
    assert resp.status_code == 200
    assert "Python fact" in resp.text


def test_memory_detail(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    resp = client.get(f"/memory/{ids[0]}")
    assert resp.status_code == 200
    assert "Test fact about Python" in resp.text
    assert "global" in resp.text


def test_memory_not_found(client: TestClient, tmp_db: Path) -> None:
    resp = client.get("/memory/nonexistent123")
    assert resp.status_code == 200
    assert "not found" in resp.text


def test_search_no_query(client: TestClient) -> None:
    resp = client.get("/search")
    assert resp.status_code == 200
    assert "Search" in resp.text


def test_search_with_query(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/search?q=Python")
    assert resp.status_code == 200
    assert "Python fact" in resp.text


def test_search_with_filters(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/search?q=SQLite&scope=project&type=decision")
    assert resp.status_code == 200
    assert "DB decision" in resp.text


def test_search_no_results(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/search?q=nonexistent_xyz")
    assert resp.status_code == 200
    assert "No results" in resp.text


def test_audit_page(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/audit")
    assert resp.status_code == 200
    assert "create" in resp.text


def test_api_memories(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/api/memories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


def test_api_memories_with_query(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/api/memories?q=Python&type=fact")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Python fact"


def test_api_memories_no_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_db_path(monkeypatch, tmp_path / "missing.db")
    app = Starlette(routes=get_web_routes())
    c = TestClient(app)
    resp = c.get("/api/memories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_filter_by_tag(client: TestClient, tmp_db: Path) -> None:
    create_memory(
        tmp_db, content="Tagged memory", scope="global", memory_type="log",
        title="Tagged", source="manual", tags=["alpha", "beta"],
    )
    create_memory(
        tmp_db, content="Untagged memory", scope="global", memory_type="log",
        title="Untagged", source="manual",
    )
    resp = client.get("/search?tags=alpha")
    assert resp.status_code == 200
    assert "Tagged" in resp.text
    assert "Untagged" not in resp.text


def test_search_filter_by_source(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/search?source=opencode")
    assert resp.status_code == 200
    assert "DB decision" in resp.text
    assert "Python fact" not in resp.text


def test_edit_memory(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    # edit form renders
    resp = client.get(f"/memory/{ids[0]}/edit")
    assert resp.status_code == 200
    assert "Test fact about Python" in resp.text
    # save edit
    resp = client.post(
        f"/memory/{ids[0]}/edit",
        data={"title": "Edited title", "content": "Edited content", "tags": "x, y"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    detail = client.get(f"/memory/{ids[0]}")
    assert "Edited title" in detail.text
    assert "Edited content" in detail.text


def test_pin_unpin_memory(client: TestClient, tmp_db: Path) -> None:
    # a 'log' memory is not pinned by default
    mid = create_memory(
        tmp_db, content="Note", scope="global", memory_type="log",
        title="Note", source="manual",
    )
    resp = client.post(f"/memory/{mid}/pin", follow_redirects=False)
    assert resp.status_code == 303
    from mem0ry.db.store import get_memory_by_id
    assert get_memory_by_id(tmp_db, mid)["pinned"] == 1
    resp = client.post(f"/memory/{mid}/unpin", follow_redirects=False)
    assert resp.status_code == 303
    assert get_memory_by_id(tmp_db, mid)["pinned"] == 0


def test_trash_and_restore(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    client.post(f"/memory/{ids[0]}/delete", follow_redirects=False)
    # deleted memory shows up in trash
    resp = client.get("/trash")
    assert resp.status_code == 200
    assert "Python fact" in resp.text
    # restore it
    resp = client.post(f"/memory/{ids[0]}/restore", follow_redirects=False)
    assert resp.status_code == 303
    from mem0ry.db.store import get_memory_by_id
    assert get_memory_by_id(tmp_db, ids[0]) is not None


def test_project_observations_page(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store import create_observation

    create_observation(
        tmp_db,
        session_id="sess-1",
        kind="session-start",
        agent="opencode",
        project_id="github.com/test/repo",
        title="Start",
        body="session started",
    )
    resp = client.get("/project/github.com/test/repo/observations")
    assert resp.status_code == 200
    assert "Start" in resp.text


def test_handoffs_page(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_handoffs import begin_handoff

    begin_handoff(
        tmp_db,
        session_id="sess-1",
        from_agent="opencode",
        summary="Continue here",
        open_questions=["what next?"],
        next_steps=["implement"],
    )
    resp = client.get("/handoffs")
    assert resp.status_code == 200
    assert "Continue here" in resp.text


def test_handoff_detail_page(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_handoffs import begin_handoff

    hid = begin_handoff(
        tmp_db,
        session_id="sess-1",
        from_agent="opencode",
        summary="Continue here",
        open_questions=["what next?"],
        next_steps=["implement"],
    )
    resp = client.get(f"/handoff/{hid}")
    assert resp.status_code == 200
    assert "Continue here" in resp.text


def test_import_page(client: TestClient) -> None:
    resp = client.get("/import")
    assert resp.status_code == 200
    assert "Import" in resp.text


def test_batch_delete_memories(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    resp = client.post(
        "/memories/batch-delete",
        data={"ids": ids},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    from mem0ry.db.connection import get_connection

    conn = get_connection(tmp_db)
    for mid in ids:
        row = conn.execute(
            "SELECT deleted_at FROM memories WHERE id = ?", (mid,)
        ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None
    conn.close()


def test_api_export_memories(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.post("/memories/export", data={"scope": "global"})
    assert resp.status_code == 200
    payload = resp.json()
    assert "memories" in payload
    assert len(payload["memories"]) == 1
    assert payload["memories"][0]["title"] == "Python fact"


def test_search_with_date_range(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/search?date_from=2020-01-01&date_to=2099-12-31&q=Python")
    assert resp.status_code == 200
    assert "Python fact" in resp.text


def test_memory_permanent_delete(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    resp = client.post(f"/memory/{ids[0]}/delete", follow_redirects=False)
    assert resp.status_code == 303
    resp = client.post(f"/memory/{ids[0]}/delete", follow_redirects=False)
    assert resp.status_code == 303


def test_observation_detail(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store import create_observation

    obs_id = create_observation(
        tmp_db,
        session_id="sess-1",
        kind="user-prompt",
        agent="opencode",
        project_id="github.com/test/repo",
        title="Prompt",
        body="hello",
    )
    resp = client.get(f"/observation/{obs_id}")
    assert resp.status_code == 200
    assert "hello" in resp.text


def test_close_and_delete_handoff(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_handoffs import begin_handoff

    hid = begin_handoff(
        tmp_db,
        session_id="sess-1",
        from_agent="opencode",
        summary="Close me",
    )
    resp = client.post(f"/handoff/{hid}/close", follow_redirects=False)
    assert resp.status_code == 303
    resp = client.post(f"/handoff/{hid}/delete", follow_redirects=False)
    assert resp.status_code == 303


def test_delete_observation(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store import create_observation

    obs_id = create_observation(
        tmp_db,
        session_id="sess-1",
        kind="log",
        agent="opencode",
        title="Log",
        body="log entry",
    )
    resp = client.post(f"/observation/{obs_id}/delete", follow_redirects=False)
    assert resp.status_code == 303


def test_edit_memory_post(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    resp = client.post(
        f"/memory/{ids[0]}/edit",
        data={"title": "Updated", "content": "New body", "tags": "a, b"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert f"/memory/{ids[0]}" in resp.headers["location"]


def test_export_page(client: TestClient, tmp_db: Path) -> None:
    _seed(tmp_db)
    resp = client.get("/export")
    assert resp.status_code == 200
    assert "Export" in resp.text or "export" in resp.text.lower()


def test_import_memories_post(client: TestClient, tmp_db: Path) -> None:
    payload = {
        "version": 1,
        "memories": [
            {
                "title": "Imported",
                "content": "body",
                "scope": "global",
                "memory_type": "fact",
                "source": "import",
                "tags": ["imported"],
            }
        ],
        "handoffs": [],
    }
    from io import BytesIO

    resp = client.post(
        "/memories/import",
        data={"project_id_override": ""},
        files={"file": ("memories.json", BytesIO(str.encode(json.dumps(payload))), "application/json")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "type=success" in resp.headers["location"]


def test_import_memories_post_invalid_json(client: TestClient, tmp_db: Path) -> None:
    from io import BytesIO

    resp = client.post(
        "/memories/import",
        data={"project_id_override": ""},
        files={"file": ("bad.json", BytesIO(b"not json"), "application/json")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "type=error" in resp.headers["location"]


def test_memory_edit_form(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    resp = client.get(f"/memory/{ids[0]}/edit")
    assert resp.status_code == 200
    assert 'name="content"' in resp.text


def test_projects_page_includes_observation_only_project(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store import create_observation

    create_observation(
        tmp_db,
        session_id="sess-1",
        kind="log",
        agent="opencode",
        project_id="only-obs-project",
        title="Obs",
        body="obs body",
    )
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert "only-obs-project" in resp.text


def test_handoffs_page_filters_by_status(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_handoffs import begin_handoff, close_handoff

    begin_handoff(tmp_db, session_id="open-sess", from_agent="opencode", summary="Open")
    closed_hid = begin_handoff(tmp_db, session_id="closed-sess", from_agent="opencode", summary="Closed")
    close_handoff(tmp_db, closed_hid)

    resp = client.get("/handoffs?status=open")
    assert resp.status_code == 200
    assert "Open" in resp.text
    assert "Closed" not in resp.text


def test_memory_detail_superseded(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_memories import create_memory
    from mem0ry.db.store import evolve_memories

    old = create_memory(tmp_db, title="Old", content="old", scope="global", memory_type="fact", source="manual")
    evolve_memories(
        tmp_db,
        old_ids=[old],
        evolved_content="Consolidated",
        rationale="test",
        title="Consolidated",
    )

    resp = client.get(f"/memory/{old}")
    assert resp.status_code == 200
    assert "evoluido" in resp.text.lower() or "Nova versao" in resp.text or "superseded" in resp.text.lower()


def test_dashboard_with_open_handoff(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_handoffs import begin_handoff

    begin_handoff(tmp_db, session_id="sess-1", from_agent="opencode", summary="Resume me")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Resume me" in resp.text


def test_trash_page_lists_deleted_memories(client: TestClient, tmp_db: Path) -> None:
    ids = _seed(tmp_db)
    client.post(f"/memory/{ids[0]}/delete", follow_redirects=False)
    resp = client.get("/trash")
    assert resp.status_code == 200
    assert "Python fact" in resp.text


def test_dashboard_handles_invalid_timestamp_gracefully(client: TestClient, tmp_db: Path) -> None:
    from mem0ry.db.store_memories import create_memory
    from mem0ry.db.connection import get_connection

    mid = create_memory(tmp_db, title="Bad time", content="C", scope="global", memory_type="fact", source="manual")
    conn = get_connection(tmp_db)
    conn.execute("UPDATE memories SET created_at = 'not-a-timestamp' WHERE id = ?", (mid,))
    conn.commit()
    conn.close()

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Bad time" in resp.text
