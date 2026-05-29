from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_FILE_RE = re.compile(r"file:\s*([^\s;]+)")
_ERROR_RE = re.compile(r"error:\s*(.+?)(?=;|$)")

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
    try:
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
    finally:
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
    try:
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
            return None

        ho = dict(row)
        now = _now_iso()
        conn.execute(
            "UPDATE handoffs SET status = 'accepted', accepted_by = ?, accepted_at = ? WHERE id = ?",
            (accepted_by, now, ho["id"]),
        )
        conn.commit()

        ho["status"] = "accepted"
        ho["accepted_by"] = accepted_by
        ho["accepted_at"] = now
    finally:
        conn.close()

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
    try:
        init_schema(conn)

        _expire_old_handoffs(conn)

        query = "SELECT * FROM handoffs WHERE status = 'open'"
        params: list[Any] = []

        if project_id:
            query += " AND (project_id = ? OR project_id IS NULL)"
            params.append(project_id)

        query += " ORDER BY created_at DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    ho = dict(row)
    ho["open_questions"] = json.loads(ho.get("open_questions") or "[]")
    ho["next_steps"] = json.loads(ho.get("next_steps") or "[]")
    return ho


def _extract_session_signals(
    chronological: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    files: list[str] = []
    errors: list[str] = []
    prompts: list[str] = []
    for obs in chronological:
        body = obs.get("body") or ""
        if obs.get("kind") == "user-prompt" and body.strip():
            prompts.append(body.strip())
        for m in _FILE_RE.findall(body):
            if m not in files:
                files.append(m)
        for m in _ERROR_RE.findall(body):
            err = m.strip()
            if err and err not in errors:
                errors.append(err)
    return files, errors, prompts


def _build_session_summary(
    observations: list[dict[str, Any]],
    user_prompts: list[str] | None,
) -> str:
    """Build a high-signal handoff summary.

    Instead of dumping every tool call, we surface what actually helps the next
    agent: what the user asked for, which files were touched, and any errors hit.
    `observations` arrives newest-first; we read them chronologically.
    """
    chronological = list(reversed(observations))
    files, errors, obs_prompts = _extract_session_signals(chronological)

    sections: list[str] = []

    # Prompts from the parsed transcript (if any) take precedence; fall back to
    # user-prompt observations (agents that emit a UserPrompt hook).
    raw_prompts = [p for p in (user_prompts or []) if p and p.strip()] or obs_prompts
    prompts = [p.strip() for p in raw_prompts if p and p.strip()]
    if prompts:
        sections.append("What the user was working on:")
        sections.extend(f"- {p[:300]}" for p in prompts[-5:])

    if files:
        sections.append("\nFiles touched:")
        sections.extend(f"- {f}" for f in files[:20])

    if errors:
        sections.append("\nErrors encountered:")
        sections.extend(f"- {e[:200]}" for e in errors[:10])

    if not sections:
        return "Session ended (no captured prompts, file edits, or errors)."

    return "\n".join(sections)


def auto_handoff_from_session(
    db_path: Path,
    session_id: str,
    agent: str,
    user_prompts: list[str] | None = None,
) -> str | None:
    observations = get_session_observations(db_path, session_id)
    if not observations:
        return None

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        existing = conn.execute(
            "SELECT id FROM handoffs WHERE session_id = ? AND status = 'open' LIMIT 1",
            (session_id,),
        ).fetchone()
    finally:
        conn.close()

    if existing:
        return None

    summary = _build_session_summary(observations, user_prompts)

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
