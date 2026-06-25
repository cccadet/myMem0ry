from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from .._helpers import _now_iso
from ..connection import get_connection
from ..retention import compute_salience
from ..schema import init_schema, next_fts_rowid
from ..store_audit import record_audit
from .crud import create_memory
from .helpers import _JOIN_AND, _NOT_SUPERSEDED, _validate_scope

logger = logging.getLogger(__name__)

_EXPORT_MEMORIES_COLUMNS = [
    "id",
    "title",
    "content",
    "scope",
    "project_id",
    "project_path",
    "context",
    "session_id",
    "memory_type",
    "source",
    "tags",
    "created_at",
    "pinned",
    "salience",
]


def export_memories(
    db_path: Path,
    *,
    scope: str | None = None,
    project_id: str | None = None,
    memory_ids: list[str] | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        conditions: list[str] = [
            "deleted_at IS NULL",
            _NOT_SUPERSEDED,
        ]
        params: list[Any] = []
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        if memory_ids:
            placeholders = ",".join("?" for _ in memory_ids)
            conditions.append(f"id IN ({placeholders})")
            params.extend(memory_ids)
        where = _JOIN_AND.join(conditions)
        cols = ", ".join(_EXPORT_MEMORIES_COLUMNS)
        rows = conn.execute(
            f"SELECT {cols} FROM memories WHERE {where} "  # nosec B608
            "ORDER BY pinned DESC, salience DESC, created_at DESC",
            params,
        ).fetchall()
    finally:
        conn.close()

    return {
        "version": 1,
        "exported_at": _now_iso(),
        "exported_by": "manual",
        "source_project_id": project_id,
        "memories": [dict(r) for r in rows],
    }


def import_memories(
    db_path: Path,
    data: dict[str, Any],
    *,
    project_id_override: str | None = None,
) -> dict[str, int]:
    version = data.get("version")
    if version != 1:
        raise ValueError(
            f"Unsupported export version '{version}'. Expected 1."
        )
    memories = data.get("memories") or []
    imported = 0
    skipped = 0
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        for mem in memories:
            orig_id = mem.get("id", "")
            if orig_id:
                row = conn.execute(
                    "SELECT id FROM memories WHERE id = ?", (orig_id,)
                ).fetchone()
                if row:
                    skipped += 1
                    continue

            new_id = orig_id or uuid.uuid4().hex[:12]
            pid = project_id_override or mem.get("project_id")
            now = _now_iso()
            raw_tags = mem.get("tags") or "[]"
            tags_json = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags

            mtype = mem.get("memory_type", "log")
            salience = compute_salience(mtype, now, 0, None)
            pinned = 1 if mtype in ("fact", "decision") else 0

            fts_rowid = next_fts_rowid(conn)
            conn.execute(
                "INSERT INTO memories(id, fts_rowid, content, scope, project_id, project_path, context, "
                "session_id, memory_type, source, tags, title, created_at, file_path, "
                "access_count, last_accessed_at, salience, pinned) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                (
                    new_id,
                    fts_rowid,
                    mem["content"],
                    mem.get("scope", "global"),
                    pid,
                    mem.get("project_path"),
                    mem.get("context"),
                    mem.get("session_id"),
                    mtype,
                    "import",
                    json.dumps(tags_json),
                    mem.get("title"),
                    now,
                    mem.get("file_path"),
                    now,
                    salience,
                    pinned,
                ),
            )
            audit_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO audit_log(id, action, target_type, target_id, agent, details, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (audit_id, "import", "memory", new_id, None, f"original_id={orig_id}", now),
            )
            imported += 1
        conn.commit()
    finally:
        conn.close()
    return {"imported": imported, "skipped": skipped}


def evolve_memories(
    db_path: Path,
    old_ids: list[str],
    evolved_content: str,
    rationale: str,
    scope: str | None = None,
    project_id: str | None = None,
    project_path: str | None = None,
    context: str | None = None,
    tags: list[str] | None = None,
    title: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """Soft-delete old facts and create a new evolved fact.

    The agent LLM provides the evolved content and rationale. This function
    handles the DB plumbing: marking old rows as superseded, creating the new
    row, and recording the audit trail.

    Returns dict with new_id, superseded_count, old_ids.
    """
    if not old_ids:
        raise ValueError("old_ids must not be empty")

    conn = get_connection(db_path)
    try:
        init_schema(conn)

        placeholders = ",".join("?" for _ in old_ids)
        old_rows = conn.execute(
            f"SELECT id, scope, project_id, project_path, context, tags, title "  # nosec B608
            f"FROM memories WHERE id IN ({placeholders}) "  # nosec B608
            f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED}",  # nosec B608
            old_ids,
        ).fetchall()

        found_ids = {r["id"] for r in old_rows}
        missing = set(old_ids) - found_ids
        if missing:
            raise ValueError(
                f"old_ids not found or already superseded/deleted: {', '.join(sorted(missing))}"
            )

        first = dict(old_rows[0])

        final_scope = _validate_scope(scope or first["scope"])
        final_title = title or first.get("title") or "Evolved fact"
        final_tags = tags if tags is not None else json.loads(first.get("tags") or "[]")
        final_project_id = project_id or first.get("project_id")
        final_project_path = project_path or first.get("project_path")
        final_context = context or first.get("context")

        new_id = create_memory(
            db_path,
            content=evolved_content,
            scope=final_scope,
            project_id=final_project_id,
            project_path=final_project_path,
            context=final_context,
            memory_type="fact",
            source=source,
            tags=final_tags,
            title=final_title,
        )

        now = _now_iso()
        conn.execute(
            f"UPDATE memories SET superseded_by = ?, deleted_at = ? "  # nosec B608
            f"WHERE id IN ({placeholders})",  # nosec B608
            [new_id, now] + old_ids,
        )
        conn.commit()
    finally:
        conn.close()

    try:
        record_audit(
            db_path,
            action="evolve",
            target_type="memory",
            target_id=new_id,
            details=json.dumps({"from": old_ids, "rationale": rationale}),
        )
    except Exception as exc:
        logger.warning("Failed to record evolve audit: %s", exc)

    return {
        "new_id": new_id,
        "superseded_count": len(old_ids),
        "old_ids": old_ids,
    }
