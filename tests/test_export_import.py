from __future__ import annotations

import json
from pathlib import Path

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import (
    create_memory,
    delete_memory,
    delete_memories_batch,
    export_memories,
    import_memories,
    begin_handoff,
    export_handoffs,
    import_handoffs,
    get_memory_by_id,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_delete_memories_batch_empty(db: Path) -> None:
    result = delete_memories_batch(db, [])
    assert result == 0


def test_delete_memories_batch_multiple(db: Path) -> None:
    id1 = create_memory(db, content="mem1", scope="global", title="M1")
    id2 = create_memory(db, content="mem2", scope="global", title="M2")
    id3 = create_memory(db, content="mem3", scope="global", title="M3")

    result = delete_memories_batch(db, [id1, id2])
    assert result == 2

    assert get_memory_by_id(db, id1) is None
    assert get_memory_by_id(db, id2) is None
    assert get_memory_by_id(db, id3) is not None


def test_delete_memories_batch_already_deleted(db: Path) -> None:
    id1 = create_memory(db, content="mem1", scope="global", title="M1")
    delete_memory(db, id1)
    result = delete_memories_batch(db, [id1])
    assert result == 0


def test_export_memories_all(db: Path) -> None:
    create_memory(db, content="mem1", scope="global", title="M1", memory_type="fact")
    create_memory(db, content="mem2", scope="project", project_id="p1", title="M2")

    data = export_memories(db)
    assert data["version"] == 1
    assert "exported_at" in data
    assert len(data["memories"]) == 2


def test_export_memories_by_scope(db: Path) -> None:
    create_memory(db, content="global1", scope="global", title="G1")
    create_memory(db, content="project1", scope="project", project_id="p1", title="P1")

    data = export_memories(db, scope="global")
    assert len(data["memories"]) == 1
    assert data["memories"][0]["scope"] == "global"


def test_export_memories_by_project(db: Path) -> None:
    create_memory(db, content="p1", scope="project", project_id="proj1", title="P1")
    create_memory(db, content="p2", scope="project", project_id="proj2", title="P2")

    data = export_memories(db, project_id="proj1")
    assert len(data["memories"]) == 1
    assert data["memories"][0]["project_id"] == "proj1"


def test_export_memories_by_ids(db: Path) -> None:
    id1 = create_memory(db, content="m1", scope="global", title="M1")
    create_memory(db, content="m2", scope="global", title="M2")

    data = export_memories(db, memory_ids=[id1])
    assert len(data["memories"]) == 1
    assert data["memories"][0]["id"] == id1


def test_export_excludes_deleted(db: Path) -> None:
    id1 = create_memory(db, content="m1", scope="global", title="M1")
    delete_memory(db, id1)

    data = export_memories(db)
    assert len(data["memories"]) == 0


def test_import_memories_basic(db: Path) -> None:
    export_data = {
        "version": 1,
        "exported_at": "2026-06-01T00:00:00",
        "exported_by": "manual",
        "memories": [
            {
                "id": "abc123",
                "title": "Imported",
                "content": "imported content",
                "scope": "global",
                "project_id": None,
                "memory_type": "fact",
                "tags": "[]",
                "source": "manual",
                "created_at": "2026-06-01T00:00:00",
                "pinned": 0,
                "salience": 0.5,
            }
        ],
    }

    result = import_memories(db, export_data)
    assert result["imported"] == 1
    assert result["skipped"] == 0

    mems = export_memories(db)
    assert len(mems["memories"]) == 1
    assert mems["memories"][0]["content"] == "imported content"


def test_import_memories_skips_duplicates(db: Path) -> None:
    export_data = {
        "version": 1,
        "exported_at": "2026-06-01T00:00:00",
        "exported_by": "manual",
        "memories": [
            {
                "id": "abc123",
                "content": "content",
                "scope": "global",
                "memory_type": "fact",
                "tags": "[]",
                "created_at": "2026-06-01T00:00:00",
                "pinned": 0,
                "salience": 0.5,
            }
        ],
    }

    import_memories(db, export_data)
    result = import_memories(db, export_data)
    assert result["imported"] == 0
    assert result["skipped"] == 1


def test_import_memories_project_override(db: Path) -> None:
    export_data = {
        "version": 1,
        "exported_at": "2026-06-01T00:00:00",
        "exported_by": "manual",
        "memories": [
            {
                "id": "xyz789",
                "content": "content",
                "scope": "project",
                "project_id": "old-project",
                "memory_type": "fact",
                "tags": "[]",
                "created_at": "2026-06-01T00:00:00",
                "pinned": 0,
                "salience": 0.5,
            }
        ],
    }

    import_memories(db, export_data, project_id_override="new-project")

    mems = export_memories(db)
    assert len(mems["memories"]) == 1
    assert mems["memories"][0]["project_id"] == "new-project"


def test_import_memories_invalid_version(db: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported export version"):
        import_memories(db, {"version": 99, "memories": []})


def test_import_memories_empty(db: Path) -> None:
    result = import_memories(db, {"version": 1, "memories": []})
    assert result["imported"] == 0
    assert result["skipped"] == 0


def test_export_import_roundtrip(db: Path) -> None:
    create_memory(
        db,
        content="important fact",
        scope="project",
        project_id="github.com/org/repo",
        title="Important",
        memory_type="fact",
        tags=["arch", "backend"],
    )
    create_memory(
        db,
        content="log entry",
        scope="session",
        session_id="sess1",
        title="Log",
        memory_type="log",
    )

    exported = export_memories(db)
    assert len(exported["memories"]) == 2

    db2 = db.parent / "import_test.db"
    conn = get_connection(db2)
    init_schema(conn)
    conn.close()

    result = import_memories(db2, exported)
    assert result["imported"] == 2
    assert result["skipped"] == 0

    re_exported = export_memories(db2)
    assert len(re_exported["memories"]) == 2


def test_export_handoffs(db: Path) -> None:
    begin_handoff(db, session_id="s1", from_agent="opencode", summary="test handoff", project_id="proj1")
    begin_handoff(db, session_id="s2", from_agent="claude-code", summary="another handoff", project_id="proj2")

    handoffs = export_handoffs(db)
    assert len(handoffs) == 2


def test_export_handoffs_by_project(db: Path) -> None:
    begin_handoff(db, session_id="s1", from_agent="opencode", summary="h1", project_id="proj1")
    begin_handoff(db, session_id="s2", from_agent="opencode", summary="h2", project_id="proj2")

    handoffs = export_handoffs(db, project_id="proj1")
    assert len(handoffs) == 1
    assert handoffs[0]["project_id"] == "proj1"


def test_import_handoffs(db: Path) -> None:
    handoffs_data = [
        {
            "session_id": "s1",
            "from_agent": "opencode",
            "summary": "imported handoff",
            "project_id": "proj1",
            "open_questions": ["what to do?"],
            "next_steps": ["finish feature"],
        }
    ]

    result = import_handoffs(db, handoffs_data)
    assert result["imported"] == 1
    assert result["skipped"] == 0

    all_handoffs = export_handoffs(db)
    assert len(all_handoffs) == 1
    assert all_handoffs[0]["summary"] == "imported handoff"


def test_import_handoffs_with_override(db: Path) -> None:
    handoffs_data = [
        {
            "session_id": "s1",
            "from_agent": "opencode",
            "summary": "handoff",
            "project_id": "old-project",
        }
    ]

    import_handoffs(db, handoffs_data, project_id_override="new-project")

    all_handoffs = export_handoffs(db)
    assert all_handoffs[0]["project_id"] == "new-project"


def test_full_roundtrip_memories_and_handoffs(db: Path) -> None:
    create_memory(db, content="shared knowledge", scope="global", title="Shared", memory_type="fact")
    begin_handoff(db, session_id="s1", from_agent="opencode", summary="pass the baton", project_id="proj1")

    exported_memories = export_memories(db)
    exported_handoffs = export_handoffs(db, project_id="proj1")
    exported_memories["handoffs"] = exported_handoffs

    db2 = db.parent / "roundtrip.db"
    conn = get_connection(db2)
    init_schema(conn)
    conn.close()

    mr = import_memories(db2, exported_memories)
    hr = import_handoffs(db2, exported_memories["handoffs"])

    assert mr["imported"] == 1
    assert hr["imported"] == 1

    all_mem = export_memories(db2)
    all_ho = export_handoffs(db2)
    assert len(all_mem["memories"]) == 1
    assert len(all_ho) == 1


def test_export_memories_columns(db: Path) -> None:
    create_memory(
        db,
        content="content here",
        scope="project",
        project_id="proj1",
        title="Titled",
        memory_type="decision",
        tags=["tag1", "tag2"],
    )

    data = export_memories(db)
    mem = data["memories"][0]
    assert "id" in mem
    assert "title" in mem
    assert "content" in mem
    assert "scope" in mem
    assert "project_id" in mem
    assert "memory_type" in mem
    assert "tags" in mem
    assert "created_at" in mem
    assert "salience" in mem
    assert "deleted_at" not in mem
    assert "grace_until" not in mem
    assert "superseded_by" not in mem
