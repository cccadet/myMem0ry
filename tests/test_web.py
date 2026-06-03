"""Tests for the web UI module."""

from __future__ import annotations

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


@pytest.fixture
def client(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("mem0ry.web.pages._db_path", lambda: tmp_db)
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
    monkeypatch.setattr("mem0ry.web.pages._db_path", lambda: tmp_path / "missing.db")
    app = Starlette(routes=get_web_routes())
    c = TestClient(app)
    c.cookies.set("lang", "en")
    resp = c.get("/")
    assert resp.status_code == 200
    assert "No database found" in resp.text


def test_default_language_is_portuguese(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mem0ry.web.pages._db_path", lambda: tmp_db)
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
    monkeypatch.setattr("mem0ry.web.pages._db_path", lambda: tmp_path / "missing.db")
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
