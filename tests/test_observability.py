"""Tests for observability tools — memory_status, memory_briefing, memory_explore."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import create_memory, record_audit, query_audit_log


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_memory_status_no_db(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_db_path", return_value=tmp_path / "missing.db"):
        result = mod.memory_status()
    assert result["total_memories"] == 0
    assert result["db_exists"] is False
    assert "uptime_seconds" in result


def test_memory_status_with_db(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    create_memory(db_path, content="test", scope="global", title="T")

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.memory_status()
    assert result["total_memories"] == 1
    assert result["db_exists"] is True
    assert result["schema_version"] == 6
    assert result["audit_entries"] >= 1


def test_memory_briefing_no_db(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_db_path", return_value=tmp_path / "missing.db"):
        result = mod.memory_briefing()
    assert result["stats"]["total"] == 0
    assert result["pinned_facts"] == []


def test_memory_briefing_with_data(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    create_memory(
        db_path, content="fact 1", scope="global",
        memory_type="fact", title="F1",
    )
    create_memory(
        db_path, content="decision 1", scope="global",
        memory_type="decision", title="D1",
    )

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.memory_briefing()
    assert result["stats"]["total"] == 2
    assert len(result["pinned_facts"]) == 1
    assert len(result["pinned_decisions"]) == 1


def test_memory_explore_no_db(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    with patch.object(mod, "_db_path", return_value=tmp_path / "missing.db"):
        result = mod.memory_explore()
    assert "No database found" in result


def test_memory_explore_with_data(tmp_path: Path) -> None:
    import mem0ry.mcp_server as mod

    db_path = _setup_db(tmp_path)
    create_memory(
        db_path, content="We chose Python", scope="global",
        memory_type="decision", title="Language Choice",
    )
    create_memory(
        db_path, content="Uses spaCy", scope="global",
        memory_type="fact", title="Stack",
    )

    with patch.object(mod, "_db_path", return_value=db_path):
        result = mod.memory_explore()
    assert "Language Choice" in result
    assert "Stack" in result
    assert "Total memories:" in result


def test_audit_record_and_query(tmp_path: Path) -> None:
    db_path = _setup_db(tmp_path)

    audit_id = record_audit(
        db_path,
        action="create",
        target_type="memory",
        target_id="abc123",
        agent="test",
        details="type=fact scope=global",
    )
    assert len(audit_id) == 12

    entries = query_audit_log(db_path)
    assert len(entries) == 1
    assert entries[0]["action"] == "create"
    assert entries[0]["target_id"] == "abc123"
    assert entries[0]["agent"] == "test"


def test_audit_query_filters(tmp_path: Path) -> None:
    db_path = _setup_db(tmp_path)

    record_audit(db_path, action="create", target_type="memory", target_id="a1")
    record_audit(db_path, action="delete", target_type="memory", target_id="a2")
    record_audit(db_path, action="create", target_type="handoff", target_id="h1")

    creates = query_audit_log(db_path, action="create")
    assert len(creates) == 2

    memory_creates = query_audit_log(db_path, action="create", target_type="memory")
    assert len(memory_creates) == 1
    assert memory_creates[0]["target_id"] == "a1"

    by_target = query_audit_log(db_path, target_id="a2")
    assert len(by_target) == 1
    assert by_target[0]["action"] == "delete"


def test_audit_auto_recorded_on_create_memory(tmp_path: Path) -> None:
    db_path = _setup_db(tmp_path)

    create_memory(
        db_path, content="auto audit", scope="global",
        memory_type="fact", title="Audited",
    )

    entries = query_audit_log(db_path, action="create", target_type="memory")
    assert len(entries) == 1
    assert "type=fact" in entries[0]["details"]
