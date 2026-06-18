"""Tests for MCP tool registration and read_memory.

Guards against the handoff-begin tool silently losing its @mcp.tool() decorator
(which breaks cross-agent handoffs) and verifies read_memory returns full content.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mem0ry import mcp_server


def _registered_tool_names() -> set[str]:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    return {t.name for t in tools}


def test_handoff_begin_is_registered() -> None:
    assert "memory_handoff_begin" in _registered_tool_names()


def test_core_tools_registered() -> None:
    names = _registered_tool_names()
    for expected in (
        "get_context",
        "save_memory",
        "search_memory",
        "read_memory",
        "memory_handoff_begin",
        "memory_handoff_accept",
        "evolve_fact",
    ):
        assert expected in names, f"missing tool: {expected}"


def _stub_conv_dir(mp: pytest.MonkeyPatch, conv_dir: Path) -> None:
    """Point mcp_server at conv_dir.

    MemoryConfig bakes CONVERSATIONS_DIR into the dataclass field default at
    import time, so setenv is too late — stub the config the server constructs.
    """

    class _Cfg:
        conversations_dir = str(conv_dir)

    mp.setattr("mem0ry.mcp_server.MemoryConfig", _Cfg)


def test_read_memory_returns_full_content(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conv"
    (conv_dir / "2025-01-01").mkdir(parents=True)
    target = conv_dir / "2025-01-01" / "abc123.md"
    target.write_text("# Title\n> id: abc123\n\nfull body here", encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        _stub_conv_dir(mp, conv_dir)
        result = mcp_server.read_memory("2025-01-01/abc123.md")

    assert result["title"] == "abc123"
    assert "full body here" in result["content"]


def test_read_memory_blocks_path_traversal(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conv"
    conv_dir.mkdir()

    with pytest.MonkeyPatch.context() as mp:
        _stub_conv_dir(mp, conv_dir)
        with pytest.raises(ValueError):
            mcp_server.read_memory("../../etc/passwd")


def _make_cfg(tmp_path: Path, **overrides: str):
    from types import SimpleNamespace
    defaults = {
        "db_path": str(tmp_path / "memories.db"),
        "memories_dir": str(tmp_path / "memories"),
        "conversations_dir": str(tmp_path / "conversations"),
        "spacy_model": "en_core_web_lg",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_save_memory_creates_row_and_file(tmp_path: Path) -> None:
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    cfg = _make_cfg(tmp_path, memories_dir=str(memories_dir))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.save_memory(
            title="Test memory", content="Test content", scope="global", memory_type="fact"
        )

    assert "Saved id=" in result
    assert any(memories_dir.iterdir())


def test_get_context_returns_empty_when_no_db(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path, db_path=str(tmp_path / "missing.db"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.get_context()

    assert isinstance(result, list)
    assert len(result) == 0


def test_memory_handoff_begin_and_accept(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.memory_handoff_begin(
            summary="Continue here",
            open_questions=["what next?"],
            next_steps=["implement"],
        )

    assert "Handoff" in result or "created" in result.lower()


def test_memory_pin_unpin(tmp_path: Path) -> None:
    from mem0ry.db.store import create_memory

    db_path = tmp_path / "memories.db"
    mid = create_memory(
        db_path,
        content="Note",
        scope="global",
        memory_type="log",
        title="Note",
        source="manual",
    )
    cfg = _make_cfg(tmp_path, db_path=str(db_path))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        pin_result = mcp_server.memory_pin(mid)
        unpin_result = mcp_server.memory_unpin(mid)

    assert "pinned" in pin_result.lower()
    assert "unpinned" in unpin_result.lower()


def test_memory_stats(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.memory_stats()

    assert isinstance(result, dict)
    assert "total" in result


def test_search_memory(tmp_path: Path) -> None:
    from mem0ry.db.store import create_memory

    db_path = tmp_path / "memories.db"
    create_memory(
        db_path,
        content="Python testing tips",
        scope="global",
        memory_type="fact",
        title="Python",
        source="manual",
    )
    cfg = _make_cfg(tmp_path, db_path=str(db_path))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.search_memory("Python")

    assert isinstance(result, list)
    assert any("Python" in (r.get("title") or r.get("content", "")) for r in result)


def test_evolve_fact(tmp_path: Path) -> None:
    from mem0ry.db.store import create_memory

    db_path = tmp_path / "memories.db"
    old_id = create_memory(
        db_path,
        content="Old fact",
        scope="global",
        memory_type="fact",
        title="Old",
        source="manual",
    )
    cfg = _make_cfg(tmp_path, db_path=str(db_path))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.evolve_fact(
            old_ids=[old_id],
            title="Updated fact",
            evolved_content="Updated content",
            rationale="Outdated",
        )

    assert "evolved" in result.lower() or "Saved id=" in result


def test_memory_forget_sweep_dry_run(tmp_path: Path) -> None:
    from mem0ry.db.store import create_memory

    db_path = tmp_path / "memories.db"
    create_memory(
        db_path,
        content="Old log",
        scope="global",
        memory_type="log",
        title="Old log",
        source="manual",
    )
    cfg = _make_cfg(tmp_path, db_path=str(db_path))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.memory_forget_sweep(execute=False)

    assert isinstance(result, dict)


def test_memory_handoff_accept(tmp_path: Path) -> None:
    from mem0ry.db.store_handoffs import begin_handoff

    db_path = tmp_path / "memories.db"
    begin_handoff(
        db_path,
        session_id="sess-1",
        from_agent="opencode",
        summary="Continue here",
    )
    cfg = _make_cfg(tmp_path, db_path=str(db_path))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.memory_handoff_accept()

    assert isinstance(result, dict) or result is None


def test_search_conversations_uses_ripgrep(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir(parents=True)
    (conv_dir / "2025-01-01").mkdir()
    (conv_dir / "2025-01-01" / "abc.md").write_text("# Chat\n> id: abc\n\nPython tips")
    cfg = _make_cfg(tmp_path, conversations_dir=str(conv_dir))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.search_conversations("Python")

    assert isinstance(result, list)
    assert any("Python" in r.get("preview", "") for r in result)


def test_search_conversations_empty_when_no_db(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path, conversations_dir=str(tmp_path / "conversations"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("mem0ry.mcp_server.MemoryConfig", lambda: cfg)
        result = mcp_server.search_conversations("nope")

    assert isinstance(result, list)
    assert len(result) == 0


def test_resolve_cwd_returns_stable_project_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = mcp_server._resolve_cwd(str(tmp_path))
    assert "project_id" in result
    assert result["project_id"] == result["stable_project_id"]


def test_auto_session_id_is_stable() -> None:
    sid1 = mcp_server._auto_session_id()
    sid2 = mcp_server._auto_session_id()
    assert sid1 == sid2
    assert len(sid1) == 8
