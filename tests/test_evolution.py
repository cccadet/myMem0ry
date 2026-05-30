"""Tests for fact evolution — evolve_memories, superseded_by, context/search exclusion."""

from __future__ import annotations

from pathlib import Path

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import (
    create_memory,
    evolve_memories,
    get_context,
    get_memory_by_id,
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


def test_evolve_memories_basic(db: Path) -> None:
    old1 = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark", tags=["tech"])
    old2 = create_memory(db, content="User migrating to Iceberg", scope="global", memory_type="fact", title="Migration", tags=["tech"])

    result = evolve_memories(
        db,
        old_ids=[old1, old2],
        evolved_content="Processing engine: Iceberg (migrated from Spark)",
        rationale="User stated migration from Spark to Iceberg",
        title="Processing engine",
    )

    assert result["superseded_count"] == 2
    assert result["old_ids"] == [old1, old2]
    assert len(result["new_id"]) == 12

    conn = get_connection(db)
    row1 = conn.execute("SELECT superseded_by, deleted_at FROM memories WHERE id = ?", (old1,)).fetchone()
    row2 = conn.execute("SELECT superseded_by, deleted_at FROM memories WHERE id = ?", (old2,)).fetchone()
    new_row = conn.execute("SELECT content, memory_type FROM memories WHERE id = ?", (result["new_id"],)).fetchone()
    conn.close()

    assert row1["superseded_by"] == result["new_id"]
    assert row1["deleted_at"] is not None
    assert row2["superseded_by"] == result["new_id"]
    assert row2["deleted_at"] is not None
    assert new_row["content"] == "Processing engine: Iceberg (migrated from Spark)"
    assert new_row["memory_type"] == "fact"


def test_evolve_memories_new_appears_in_context(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    result = evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    ctx = get_context(db, top_k=5)
    ids = [r["id"] for r in ctx]
    assert result["new_id"] in ids


def test_evolve_memories_old_hidden_from_context(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    ctx = get_context(db, top_k=5)
    ids = [r["id"] for r in ctx]
    assert old not in ids


def test_evolve_memories_old_hidden_from_search(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    results = search_memories(db, query="Spark")
    ids = [r["id"] for r in results]
    assert old not in ids


def test_evolve_memories_read_old_by_id_still_works(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    result = evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    assert get_memory_by_id(db, old) is None

    conn = get_connection(db)
    row = conn.execute("SELECT superseded_by FROM memories WHERE id = ?", (old,)).fetchone()
    conn.close()
    assert row["superseded_by"] == result["new_id"]


def test_evolve_memories_inherits_tags(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark", tags=["tech", "processing"])

    result = evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    new_mem = get_memory_by_id(db, result["new_id"])
    import json
    tags = json.loads(new_mem["tags"])
    assert "tech" in tags
    assert "processing" in tags


def test_evolve_memories_inherits_scope(db: Path) -> None:
    old = create_memory(
        db, content="Project uses Spark", scope="project",
        project_id="github.com/x/y", memory_type="fact", title="Spark",
    )

    result = evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Project uses Iceberg",
        rationale="Migration",
    )

    new_mem = get_memory_by_id(db, result["new_id"])
    assert new_mem["scope"] == "project"
    assert new_mem["project_id"] == "github.com/x/y"


def test_evolve_memories_custom_tags_override(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark", tags=["old"])

    result = evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
        tags=["new", "iceberg"],
    )

    new_mem = get_memory_by_id(db, result["new_id"])
    import json
    tags = json.loads(new_mem["tags"])
    assert "new" in tags
    assert "iceberg" in tags
    assert "old" not in tags


def test_evolve_memories_audit_logged(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    result = evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="User explicitly stated migration",
    )

    conn = get_connection(db)
    row = conn.execute(
        "SELECT action, target_id, details FROM audit_log WHERE action = 'evolve' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["action"] == "evolve"
    assert row["target_id"] == result["new_id"]
    assert "rationale" in row["details"]


def test_evolve_memories_already_superseded_fails(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    with pytest.raises(ValueError, match="not found or already superseded"):
        evolve_memories(
            db,
            old_ids=[old],
            evolved_content="Processing engine: Flink",
            rationale="Another migration",
        )


def test_evolve_memories_not_found_fails(db: Path) -> None:
    with pytest.raises(ValueError, match="not found or already superseded"):
        evolve_memories(
            db,
            old_ids=["nonexistent"],
            evolved_content="Something",
            rationale="Test",
        )


def test_evolve_memories_empty_old_ids_fails(db: Path) -> None:
    with pytest.raises(ValueError, match="old_ids must not be empty"):
        evolve_memories(
            db,
            old_ids=[],
            evolved_content="Something",
            rationale="Test",
        )


def test_stats_includes_superseded_in_total(db: Path) -> None:
    old = create_memory(db, content="User uses Spark", scope="global", memory_type="fact", title="Spark")

    evolve_memories(
        db,
        old_ids=[old],
        evolved_content="Processing engine: Iceberg",
        rationale="Migration",
    )

    s = stats(db)
    assert s["total"] == 2
