"""Tests for db.retention — salience scoring, pin/unpin, forget sweep."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.retention import (
    _GRACE_DAYS,
    compute_salience,
    forget_sweep,
    pin_memory,
    tier_from_type,
    unpin_memory,
    update_salience_for_all,
)
from mem0ry.db.schema import init_schema
from mem0ry.db.store import create_memory


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def _insert_old_memory(
    db_path: Path,
    memory_type: str = "log",
    days_old: int = 100,
    access_count: int = 0,
    scope: str = "session",
    pinned: int | None = None,
) -> str:
    past = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    mem_id = create_memory(
        db_path,
        content=f"old {memory_type}",
        scope=scope,
        memory_type=memory_type,
        title=f"Old {memory_type}",
    )
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE memories SET created_at = ?, access_count = ? WHERE id = ?",
        (past, access_count, mem_id),
    )
    if pinned is not None:
        conn.execute(
            "UPDATE memories SET pinned = ? WHERE id = ?", (pinned, mem_id)
        )
    conn.commit()
    conn.close()
    return mem_id


def test_tier_from_type() -> None:
    assert tier_from_type("log") == "working"
    assert tier_from_type("pattern") == "procedural"
    assert tier_from_type("fact") == "semantic"
    assert tier_from_type("decision") == "semantic"


def test_tier_from_type_unknown() -> None:
    assert tier_from_type("unknown") == "working"


def test_compute_salience_fresh() -> None:
    now = datetime.now(timezone.utc).isoformat()
    s = compute_salience("log", now, 0, None)
    assert s > 0.0
    assert s < 1.0


def test_compute_salience_old_log_decays() -> None:
    now = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    fresh = compute_salience("log", now, 0, None)
    stale = compute_salience("log", old, 0, None)
    assert stale < fresh


def test_compute_salience_fact_higher_than_log() -> None:
    ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    fact_s = compute_salience("fact", ts, 0, None)
    log_s = compute_salience("log", ts, 0, None)
    assert fact_s > log_s


def test_compute_salience_access_count_boosts() -> None:
    ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    low = compute_salience("log", ts, 0, ts)
    high = compute_salience("log", ts, 50, ts)
    assert high > low


def test_compute_salience_invalid_date() -> None:
    s = compute_salience("log", "not-a-date", 0, None)
    assert s == pytest.approx(0.5)


def test_pin_memory(db: Path) -> None:
    mem_id = _insert_old_memory(db, memory_type="log")
    result = pin_memory(db, mem_id)
    assert result is True

    conn = get_connection(db)
    row = conn.execute("SELECT pinned FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()
    assert row["pinned"] == 1


def test_pin_memory_not_found(db: Path) -> None:
    result = pin_memory(db, "nonexistent")
    assert result is False


def test_unpin_memory(db: Path) -> None:
    mem_id = _insert_old_memory(db, memory_type="fact")
    result = unpin_memory(db, mem_id)
    assert result is True

    conn = get_connection(db)
    row = conn.execute("SELECT pinned FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()
    assert row["pinned"] == 0


def test_unpin_memory_not_found(db: Path) -> None:
    result = unpin_memory(db, "nonexistent")
    assert result is False


def test_forget_sweep_dry_run(db: Path) -> None:
    _insert_old_memory(db, memory_type="log", days_old=200)
    _insert_old_memory(db, memory_type="log", days_old=5)

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 1
    assert result["hard_count"] == 0

    conn = get_connection(db)
    count = conn.execute("SELECT count(*) FROM memories WHERE deleted_at IS NULL").fetchone()[0]
    conn.close()
    assert count == 2


def test_forget_sweep_executes_soft_delete(db: Path) -> None:
    _insert_old_memory(db, memory_type="log", days_old=200)

    result = forget_sweep(db, dry_run=False)
    assert result["soft_count"] == 1

    conn = get_connection(db)
    row = conn.execute("SELECT deleted_at, grace_until FROM memories").fetchone()
    conn.close()
    assert row["deleted_at"] is not None
    assert row["grace_until"] is not None


def test_forget_sweep_preserves_pinned(db: Path) -> None:
    _insert_old_memory(db, memory_type="fact", days_old=500)

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 0


def test_forget_sweep_preserves_recent(db: Path) -> None:
    _insert_old_memory(db, memory_type="log", days_old=5)

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 0


def test_forget_sweep_preserves_patterns_longer(db: Path) -> None:
    _insert_old_memory(db, memory_type="pattern", days_old=100)

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 0


def test_forget_sweep_deletes_patterns_after_365d(db: Path) -> None:
    _insert_old_memory(db, memory_type="pattern", days_old=400)

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 1


def test_forget_sweep_hard_deletes_expired(db: Path) -> None:
    mem_id = _insert_old_memory(db, memory_type="log", days_old=200)

    conn = get_connection(db)
    past_grace = (
        datetime.now(timezone.utc) - timedelta(days=_GRACE_DAYS + 1)
    ).isoformat()
    conn.execute(
        "UPDATE memories SET deleted_at = ?, grace_until = ? WHERE id = ?",
        (past_grace, past_grace, mem_id),
    )
    conn.commit()
    conn.close()

    result = forget_sweep(db, dry_run=False)
    assert result["hard_count"] == 1

    conn = get_connection(db)
    count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
    conn.close()
    assert count == 0


def test_forget_sweep_high_access_count_preserves(db: Path) -> None:
    _insert_old_memory(db, memory_type="log", days_old=200, access_count=500)

    result = forget_sweep(db, dry_run=True)
    assert result["soft_count"] == 0


def test_update_salience_for_all(db: Path) -> None:
    create_memory(db, content="a", scope="global", memory_type="log", title="A")
    create_memory(db, content="b", scope="global", memory_type="fact", title="B")

    count = update_salience_for_all(db)
    assert count == 2

    conn = get_connection(db)
    rows = conn.execute("SELECT id, salience FROM memories").fetchall()
    conn.close()
    for row in rows:
        assert row["salience"] > 0.0


def test_create_memory_auto_pins_fact(db: Path) -> None:
    mem_id = create_memory(
        db, content="a fact", scope="global", memory_type="fact", title="F"
    )
    conn = get_connection(db)
    row = conn.execute("SELECT pinned FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()
    assert row["pinned"] == 1


def test_create_memory_auto_pins_decision(db: Path) -> None:
    mem_id = create_memory(
        db, content="a decision", scope="global", memory_type="decision", title="D"
    )
    conn = get_connection(db)
    row = conn.execute("SELECT pinned FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()
    assert row["pinned"] == 1


def test_create_memory_does_not_pin_log(db: Path) -> None:
    mem_id = create_memory(
        db, content="a log", scope="global", memory_type="log", title="L"
    )
    conn = get_connection(db)
    row = conn.execute("SELECT pinned FROM memories WHERE id = ?", (mem_id,)).fetchone()
    conn.close()
    assert row["pinned"] == 0
