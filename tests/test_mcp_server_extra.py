"""Extra tests for mcp_server tools and HTTP endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_search_memory_returns_results(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod
    from mem0ry.db.store import create_memory

    db_path = _setup_db(tmp_path)
    create_memory(
        db_path, content="python testing", scope="global", memory_type="fact", title="T1"
    )

    with (
        patch.object(mod, "_db_path", return_value=db_path),
        patch.object(mod, "_get_expander", side_effect=Exception("no model")),
    ):
        result = mod.search_memory("python", top_k=5, cwd=str(tmp_path))

    assert len(result) >= 1
    assert result[0]["title"] == "T1"


def test_search_memory_no_db(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_db_path", return_value=tmp_path / "missing.db"):
        result = mod.search_memory("python", cwd=str(tmp_path))
    assert result == []


def test_search_conversations_ripgrep(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    conv = tmp_path / "conv"
    conv.mkdir()
    (conv / "chat.md").write_text("python chat", encoding="utf-8")

    with (
        patch.object(mod, "_conversations_dir", return_value=conv),
        patch.object(mod, "_get_expander", side_effect=Exception("no model")),
        patch("mem0ry.conversations.search.search", return_value=[conv / "chat.md"]),
    ):
        result = mod.search_conversations("python", backend="ripgrep")

    assert len(result) == 1
    assert result[0]["path"] == "chat.md"


def test_search_conversations_bm25(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    conv = tmp_path / "conv"
    conv.mkdir()
    (conv / "chat.md").write_text("python chat", encoding="utf-8")

    with (
        patch.object(mod, "_conversations_dir", return_value=conv),
        patch.object(mod, "_get_expander", side_effect=Exception("no model")),
        patch("mem0ry.conversations.search_bm25.search_bm25", return_value=[conv / "chat.md"]),
    ):
        result = mod.search_conversations("python", backend="bm25")

    assert len(result) == 1


@patch("mem0ry.conversations.embeddings.SpacyEncoder")
@patch("mem0ry.conversations.vector_store.VectorStore")
@patch("mem0ry.conversations.search_hybrid.search_hybrid")
def test_search_conversations_hybrid(
    mock_hybrid: MagicMock,
    mock_store_cls: MagicMock,
    _mock_encoder_cls: MagicMock,
    tmp_path: Path,
) -> None:
    import mem0ry.mcp_server as mod

    conv = tmp_path / "conv"
    conv.mkdir()
    (conv / "chat.md").write_text("python chat", encoding="utf-8")
    mock_hybrid.return_value = [conv / "chat.md"]
    mock_store = MagicMock()
    mock_store_cls.return_value = mock_store

    with (
        patch.object(mod, "_conversations_dir", return_value=conv),
        patch.object(mod, "_get_expander", side_effect=Exception("no model")),
    ):
        result = mod.search_conversations("python", backend="hybrid")

    assert len(result) == 1
    mock_store.close.assert_called_once()


def test_search_conversations_missing_dir(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_conversations_dir", return_value=tmp_path / "missing"):
        result = mod.search_conversations("python")
    assert result == []


def test_read_memory_by_id(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod
    from mem0ry.db.store import create_memory

    db_path = _setup_db(tmp_path)
    mem_id = create_memory(
        db_path, content="content", scope="global", memory_type="fact", title="T"
    )

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.read_memory(mem_id)

    assert result["id"] == mem_id
    assert result["title"] == "T"


def test_read_memory_by_path(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    conv = tmp_path / "conv"
    conv.mkdir()
    (conv / "chat.md").write_text("hello", encoding="utf-8")

    with patch.object(mod, "_conversations_dir", return_value=conv):
        result = mod.read_memory("chat.md")

    assert result["content"] == "hello"


def test_read_memory_missing_id(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    with patch.object(mod, "_db_path", return_value=db_path):
        with pytest.raises(ValueError, match="Memory not found"):
            mod.read_memory("nonexistent")


def test_read_memory_missing_conv_dir(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_conversations_dir", return_value=tmp_path / "missing"):
        with pytest.raises(ValueError, match="No conversations directory"):
            mod.read_memory("chat.md")


def test_handoff_begin_and_accept(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.memory_handoff_begin(
            "summary", open_questions=["q1"], next_steps=["s1"], cwd=str(tmp_path)
        )
    assert "Handoff" in result

    with patch.object(mod, "_db_path", return_value=db_path):
        ho = mod.memory_handoff_accept(cwd=str(tmp_path))
    assert ho is not None
    assert ho["summary"] == "summary"


def test_pin_unpin_memory(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod
    from mem0ry.db.store import create_memory

    db_path = _setup_db(tmp_path)
    mem_id = create_memory(
        db_path, content="x", scope="global", memory_type="fact", title="T"
    )

    with patch.object(mod, "_db_path", return_value=db_path):
        assert "Pinned" in mod.memory_pin(mem_id)
        assert "Unpinned" in mod.memory_unpin(mem_id)


def test_forget_sweep_preview(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod
    from mem0ry.db.store import create_memory

    db_path = _setup_db(tmp_path)
    create_memory(db_path, content="x", scope="session", memory_type="log", title="L")

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.memory_forget_sweep(execute=False)

    assert "soft_deleted" in result


def test_evolve_fact(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod
    from mem0ry.db.store import create_memory

    db_path = _setup_db(tmp_path)
    old_id = create_memory(
        db_path, content="old fact", scope="global", memory_type="fact", title="Old"
    )

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.evolve_fact(
            old_ids=[old_id],
            evolved_content="new fact",
            rationale="updated",
            title="New",
            cwd=str(tmp_path),
        )

    assert "Evolved fact" in result


def test_version() -> None:
    from mem0ry.mcp_server import _version

    assert _version() not in ("", None)


@pytest.mark.anyio
async def test_health_endpoint(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    request = MagicMock()

    with patch.object(mod, "_db_path", return_value=db_path):
        response = await mod.health_endpoint(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["status"] == "ok"


@pytest.mark.anyio
async def test_hook_endpoint(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    request = AsyncMock()
    request.json = AsyncMock(return_value={
        "kind": "log",
        "session_id": "sess-1",
        "agent": "test",
        "body": "hello",
    })

    with patch.object(mod, "_db_path", return_value=db_path):
        response = await mod.hook_endpoint(request)

    assert response.status_code == 202


@pytest.mark.anyio
async def test_hook_endpoint_invalid_json(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    request = AsyncMock()
    request.json = AsyncMock(side_effect=ValueError("bad json"))

    response = await mod.hook_endpoint(request)
    assert response.status_code == 400


@pytest.mark.anyio
async def test_hook_endpoint_missing_session(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    request = AsyncMock()
    request.json = AsyncMock(return_value={"kind": "log"})

    response = await mod.hook_endpoint(request)
    assert response.status_code == 400


@pytest.mark.anyio
async def test_handoff_accept_endpoint(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    from mem0ry.db.store import begin_handoff

    begin_handoff(
        db_path,
        session_id="sess-1",
        from_agent="test",
        summary="s",
        project_id=None,
        project_path=None,
        context=None,
    )

    request = MagicMock()
    request.query_params = {}

    with patch.object(mod, "_db_path", return_value=db_path):
        response = await mod.handoff_accept_endpoint(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["summary"] == "s"


@pytest.mark.anyio
async def test_context_endpoint(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod
    from mem0ry.db.store import create_memory

    db_path = _setup_db(tmp_path)
    create_memory(
        db_path, content="global fact", scope="global", memory_type="fact", title="G"
    )

    request = MagicMock()
    request.query_params = {"cwd": str(tmp_path), "top_k": "5"}

    with patch.object(mod, "_db_path", return_value=db_path):
        response = await mod.context_endpoint(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert len(body) >= 1


@pytest.mark.anyio
async def test_context_endpoint_no_db(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    request = MagicMock()
    request.query_params = {"cwd": str(tmp_path)}

    with patch.object(mod, "_db_path", return_value=tmp_path / "missing.db"):
        response = await mod.context_endpoint(request)

    assert response.status_code == 200
    assert json.loads(response.body) == []


def test_write_runtime_file(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    cfg = MagicMock()
    cfg.spool_dir = str(tmp_path / "spool")
    cfg.server_host = "127.0.0.1"
    cfg.server_port = 49374

    with (
        patch.object(mod, "_runtime_file", return_value=tmp_path / "runtime"),
        patch.object(mod, "MemoryConfig", return_value=cfg),
    ):
        mod._write_runtime_file()

    assert (tmp_path / "runtime").exists()


def test_drain_spool(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "event.json").write_text(
        json.dumps({"session_id": "sess-1", "kind": "log", "body": "x"}),
        encoding="utf-8",
    )
    (spool / "bad.json").write_text("not json", encoding="utf-8")

    cfg = MagicMock()
    cfg.spool_dir = str(spool)

    with (
        patch.object(mod, "_db_path", return_value=db_path),
        patch.object(mod, "MemoryConfig", return_value=cfg),
    ):
        handled = mod._drain_spool_once()

    assert handled == 1
    assert not (spool / "event.json").exists()
    assert not (spool / "bad.json").exists()
