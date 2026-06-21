from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from .._helpers import _now_iso
from ..connection import get_connection
from ..doltlite_sync import maybe_auto_commit
from ..schema import init_schema
from ..store_audit import record_audit
from .helpers import _validate_memory_type, _validate_scope, _validate_source

logger = logging.getLogger(__name__)


def create_memory(
    db_path: Path,
    content: str,
    scope: str = "global",
    project_id: str | None = None,
    project_path: str | None = None,
    context: str | None = None,
    session_id: str | None = None,
    memory_type: str = "log",
    source: str = "manual",
    tags: list[str] | None = None,
    title: str | None = None,
    file_path: str | None = None,
) -> str:
    _validate_scope(scope)
    _validate_source(source)
    _validate_memory_type(memory_type)
    mem_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    tags_json = json.dumps(tags or [])

    from ..retention import compute_salience
    from ..schema import next_fts_rowid

    salience = compute_salience(memory_type, now, 0, None)
    pinned = 1 if memory_type in ("fact", "decision") else 0

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        fts_rowid = next_fts_rowid(conn)
        conn.execute(
            "INSERT INTO memories(id, fts_rowid, content, scope, project_id, project_path, context, "
            "session_id, memory_type, source, tags, title, created_at, file_path, "
            "access_count, last_accessed_at, salience, pinned) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
            (
                mem_id,
                fts_rowid,
                content,
                scope,
                project_id,
                project_path,
                context,
                session_id,
                memory_type,
                source,
                tags_json,
                title,
                now,
                file_path,
                now,
                salience,
                pinned,
            ),
        )
        conn.commit()
        maybe_auto_commit(conn)
    finally:
        conn.close()

    try:
        record_audit(
            db_path,
            action="create",
            target_type="memory",
            target_id=mem_id,
            details=f"type={memory_type} scope={scope}",
        )
    except Exception as exc:
        logger.warning("Failed to record create audit: %s", exc)

    return mem_id


def get_memory_by_id(db_path: Path, memory_id: str) -> dict[str, Any] | None:
    """Fetch a single (non-deleted) memory by id, tracking the read."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ? AND deleted_at IS NULL",
            (memory_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    from .lifecycle import track_reads

    track_reads(db_path, [memory_id])
    return dict(row)


def update_memory(
    db_path: Path,
    memory_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Update an existing (non-deleted) memory's editable fields.

    Only ``title``, ``content`` and ``tags`` are user-editable from the web UI;
    everything else (scope, salience, lineage) is managed by the system.
    """
    sets: list[str] = []
    params: list[Any] = []
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if content is not None:
        sets.append("content = ?")
        params.append(content)
    if tags is not None:
        sets.append("tags = ?")
        params.append(json.dumps(tags))
    if not sets:
        return False

    now = _now_iso()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(memory_id)

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        cursor = conn.execute(
            f"UPDATE memories SET {', '.join(sets)} WHERE id = ? AND deleted_at IS NULL",  # nosec B608
            params,
        )
        conn.commit()
        maybe_auto_commit(conn)
        affected = cursor.rowcount
    finally:
        conn.close()

    if affected > 0:
        try:
            record_audit(
                db_path,
                action="update",
                target_type="memory",
                target_id=memory_id,
            )
        except Exception as exc:
            logger.warning("Failed to record update audit: %s", exc)

    return affected > 0


def list_deleted_memories(db_path: Path, top_k: int = 200) -> list[dict[str, Any]]:
    """List soft-deleted memories (the trash), most recently deleted first."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        rows = conn.execute(
            "SELECT * FROM memories WHERE deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC LIMIT ?",
            (top_k,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def restore_memory(db_path: Path, memory_id: str) -> bool:
    """Bring a soft-deleted memory back, clearing its grace period."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        cursor = conn.execute(
            "UPDATE memories SET deleted_at = NULL, grace_until = NULL "
            "WHERE id = ? AND deleted_at IS NOT NULL",
            (memory_id,),
        )
        conn.commit()
        maybe_auto_commit(conn)
        affected = cursor.rowcount
    finally:
        conn.close()

    if affected > 0:
        try:
            record_audit(
                db_path,
                action="restore",
                target_type="memory",
                target_id=memory_id,
            )
        except Exception as exc:
            logger.warning("Failed to record restore audit: %s", exc)

    return affected > 0


def delete_memory(db_path: Path, memory_id: str) -> bool:
    conn = get_connection(db_path)
    init_schema(conn)
    now = _now_iso()
    cursor = conn.execute(
        "UPDATE memories SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
        (now, memory_id),
    )
    conn.commit()
    maybe_auto_commit(conn)
    affected = cursor.rowcount
    conn.close()

    if affected > 0:
        try:
            record_audit(
                db_path,
                action="delete",
                target_type="memory",
                target_id=memory_id,
            )
        except Exception as exc:
            logger.warning("Failed to record delete audit: %s", exc)

    return affected > 0
