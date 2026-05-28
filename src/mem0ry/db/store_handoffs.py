from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema
from ._helpers import _now_iso
from .store_audit import record_audit
from .store_observations import get_session_observations

_HANDOFF_EXPIRE_DAYS = 7


def begin_handoff(
    db_path: Path,
    session_id: str,
    from_agent: str,
    summary: str,
    project_id: str | None = None,
    project_path: str | None = None,
    context: str | None = None,
    open_questions: list[str] | None = None,
    next_steps: list[str] | None = None,
) -> str:
    ho_id = uuid.uuid4().hex[:12]
    now = _now_iso()

    expires = (
        datetime.now(timezone.utc) + timedelta(days=_HANDOFF_EXPIRE_DAYS)
    ).isoformat()

    oq_json = json.dumps(open_questions or [])
    ns_json = json.dumps(next_steps or [])

    conn = get_connection(db_path)
    init_schema(conn)
    conn.execute(
        "INSERT INTO handoffs(id, session_id, from_agent, project_id, project_path, "
        "context, status, summary, open_questions, next_steps, created_at, expires_at) "
        "VALUES(?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)",
        (
            ho_id,
            session_id,
            from_agent,
            project_id,
            project_path,
            context,
            summary,
            oq_json,
            ns_json,
            now,
            expires,
        ),
    )
    conn.commit()
    conn.close()

    try:
        record_audit(
            db_path,
            action="begin_handoff",
            target_type="handoff",
            target_id=ho_id,
            agent=from_agent,
            details=summary[:200],
        )
    except Exception:
        pass

    return ho_id


def accept_handoff(
    db_path: Path,
    project_id: str | None,
    accepted_by: str | None = None,
) -> dict[str, Any] | None:
    conn = get_connection(db_path)
    init_schema(conn)

    _expire_old_handoffs(conn)

    query = "SELECT * FROM handoffs WHERE status = 'open'"
    params: list[Any] = []

    if project_id:
        query += " AND (project_id = ? OR project_id IS NULL)"
        params.append(project_id)

    query += " ORDER BY created_at DESC LIMIT 1"

    row = conn.execute(query, params).fetchone()
    if not row:
        conn.close()
        return None

    ho = dict(row)
    now = _now_iso()
    conn.execute(
        "UPDATE handoffs SET status = 'accepted', accepted_by = ?, accepted_at = ? WHERE id = ?",
        (accepted_by, now, ho["id"]),
    )
    conn.commit()
    conn.close()

    ho["status"] = "accepted"
    ho["accepted_by"] = accepted_by
    ho["accepted_at"] = now
    ho["open_questions"] = json.loads(ho.get("open_questions") or "[]")
    ho["next_steps"] = json.loads(ho.get("next_steps") or "[]")

    try:
        record_audit(
            db_path,
            action="accept_handoff",
            target_type="handoff",
            target_id=ho["id"],
            agent=accepted_by,
        )
    except Exception:
        pass

    return ho


def pending_handoff(
    db_path: Path,
    project_id: str | None,
) -> dict[str, Any] | None:
    conn = get_connection(db_path)
    init_schema(conn)

    _expire_old_handoffs(conn)

    query = "SELECT * FROM handoffs WHERE status = 'open'"
    params: list[Any] = []

    if project_id:
        query += " AND (project_id = ? OR project_id IS NULL)"
        params.append(project_id)

    query += " ORDER BY created_at DESC LIMIT 1"

    row = conn.execute(query, params).fetchone()
    conn.close()
    if not row:
        return None

    ho = dict(row)
    ho["open_questions"] = json.loads(ho.get("open_questions") or "[]")
    ho["next_steps"] = json.loads(ho.get("next_steps") or "[]")
    return ho


def auto_handoff_from_session(db_path: Path, session_id: str, agent: str) -> str | None:
    observations = get_session_observations(db_path, session_id)
    if not observations:
        return None

    conn = get_connection(db_path)
    init_schema(conn)
    existing = conn.execute(
        "SELECT id FROM handoffs WHERE session_id = ? AND status = 'open' LIMIT 1",
        (session_id,),
    ).fetchone()
    conn.close()
    if existing:
        return None

    parts: list[str] = []
    for obs in observations[:20]:
        kind = obs.get("kind", "")
        body = obs.get("body") or obs.get("title") or ""
        if body:
            parts.append(f"[{kind}] {body[:200]}")

    summary = "\n".join(parts) if parts else "Session ended."

    first = observations[0]
    return begin_handoff(
        db_path,
        session_id=session_id,
        from_agent=agent,
        summary=summary[:2000],
        project_id=first.get("project_id"),
        project_path=first.get("cwd"),
    )


def _expire_old_handoffs(conn: sqlite3.Connection) -> None:
    now = _now_iso()
    conn.execute(
        "UPDATE handoffs SET status = 'expired' "
        "WHERE status = 'open' AND expires_at IS NOT NULL AND expires_at < ?",
        (now,),
    )
    conn.commit()
