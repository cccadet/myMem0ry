from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .._helpers import _now_iso
from ..connection import get_connection
from ..retention import forget_sweep, pin_memory, unpin_memory
from ..schema import init_schema
from ..store_audit import record_audit
from .crud import create_memory

logger = logging.getLogger(__name__)

__all__ = [
    "end_session",
    "pin_memory",
    "unpin_memory",
    "touch_memory",
    "track_reads",
    "delete_memories_batch",
    "decay_memories",
]


def end_session(db_path: Path, session_id: str, summary: str | None = None) -> bool:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        rows = conn.execute(
            "SELECT id FROM memories WHERE session_id = ?", (session_id,)
        ).fetchall()

        if not rows:
            return False

        now = _now_iso()
        for row in rows:
            conn.execute(
                "UPDATE memories SET updated_at = ? WHERE id = ?", (now, row["id"])
            )
        conn.commit()
    finally:
        conn.close()

    if summary:
        create_memory(
            db_path,
            content=summary,
            scope="session",
            session_id=session_id,
            source="manual",
            title=f"Session summary: {session_id}",
            memory_type="log",
        )

    try:
        record_audit(
            db_path,
            action="end_session",
            target_type="session",
            target_id=session_id,
            details=summary[:200] if summary else None,
        )
    except Exception as exc:
        logger.warning("Failed to record end_session audit: %s", exc)

    return True


def touch_memory(db_path: Path, memory_id: str) -> bool:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        now = _now_iso()
        cursor = conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
            (now, memory_id),
        )
        conn.commit()
        affected = cursor.rowcount
    finally:
        conn.close()
    return affected > 0


def _track_reads_sync(db_path: Path, memory_ids: list[str]) -> None:
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        now = _now_iso()
        for mid in memory_ids:
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (now, mid),
            )
        conn.commit()
    except Exception as exc:
        logger.warning("Failed to track memory reads: %s", exc)
    finally:
        conn.close()


def track_reads(db_path: Path, memory_ids: list[str]) -> None:
    if not memory_ids:
        return
    threading.Thread(target=_track_reads_sync, args=(db_path, memory_ids), daemon=True).start()


def delete_memories_batch(db_path: Path, memory_ids: list[str]) -> int:
    if not memory_ids:
        return 0

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        now = _now_iso()
        grace = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()
        placeholders = ",".join("?" for _ in memory_ids)
        cursor = conn.execute(
            f"UPDATE memories SET deleted_at = ?, grace_until = ? "  # nosec B608
            f"WHERE id IN ({placeholders}) AND deleted_at IS NULL",  # nosec B608
            [now, grace] + memory_ids,
        )
        affected = cursor.rowcount
        for mid in memory_ids:
            audit_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO audit_log(id, action, target_type, target_id, agent, details, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (audit_id, "delete", "memory", mid, None, "batch", now),
            )
        conn.commit()
    finally:
        conn.close()
    return affected


def decay_memories(
    db_path: Path, dry_run: bool = False
) -> list[str]:
    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    soft = result.get("soft_deleted", [])
    return [str(m["id"]) for m in soft]
