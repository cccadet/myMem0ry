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
