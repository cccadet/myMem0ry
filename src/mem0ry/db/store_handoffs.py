from __future__ import annotations

import json
import re
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

_FILE_RE = re.compile(r"file:\s*([^\s;]+)")
_ERROR_RE = re.compile(r"error:\s*(.+)(?=;|$)")

_HANDOFF_EXPIRE_DAYS = 7

# Slash-command / local-command wrappers that Claude Code writes into the
# transcript as `user` messages. They are harness boilerplate, not user intent,
# so they must not leak into the handoff summary.
_COMMAND_WRAPPER_RE = re.compile(
    r"</?(?:local-command-caveat|local-command-stdout|local-command-stderr|"
    r"command-name|command-message|command-args)>",
    re.IGNORECASE,
)
# Prompts longer than this are almost always pasted blobs (code, HTML, logs).
# We keep a short, labelled marker instead of dumping the head of the blob.
_PASTE_THRESHOLD = 600


def _clean_prompts(prompts: list[str] | None) -> list[str]:
    """Strip harness noise from raw user prompts before summarizing.

    Two kinds of noise pollute the auto-handoff summary: slash-command wrapper
    messages (e.g. the `/clear` boilerplate) and large pasted blobs. The first
    is dropped entirely; the second is replaced by a compact `[pasted content,
    ~N chars]` marker so the summary records that a paste happened without
    reproducing it.
    """
    cleaned: list[str] = []
    for raw in prompts or []:
        text = (raw or "").strip()
        if not text:
            continue
        if _COMMAND_WRAPPER_RE.search(text):
            continue
        if len(text) > _PASTE_THRESHOLD:
            first_line = text.splitlines()[0].strip()
            head = first_line[:80] if first_line else ""
            marker = f"[pasted content, ~{len(text)} chars]"
            cleaned.append(f"{head} {marker}".strip() if head else marker)
            continue
        cleaned.append(text)
    return cleaned


def _collect_unique(lst: list[str], item: str) -> None:
    if item and item not in lst:
        lst.append(item)


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
            _collect_unique(files, m)
        for m in _ERROR_RE.findall(body):
            _collect_unique(errors, m.strip())
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
    # user-prompt observations (agents that emit a UserPrompt hook). Both paths
    # are cleaned of harness boilerplate and pasted blobs before summarizing.
    raw_prompts = _clean_prompts(user_prompts) or _clean_prompts(obs_prompts)
    prompts = raw_prompts
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


def export_handoffs(
    db_path: Path,
    *,
    project_id: str | None = None,
    handoff_ids: list[str] | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        conditions: list[str] = ["1=1"]
        params: list[Any] = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if handoff_ids:
            placeholders = ",".join("?" for _ in handoff_ids)
            conditions.append(f"id IN ({placeholders})")
            params.extend(handoff_ids)
        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM handoffs WHERE {where} ORDER BY created_at DESC",
            params,
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["open_questions"] = json.loads(d.get("open_questions") or "[]")
        d["next_steps"] = json.loads(d.get("next_steps") or "[]")
        result.append(d)
    return result


def import_handoffs(
    db_path: Path,
    handoffs: list[dict[str, Any]],
    *,
    project_id_override: str | None = None,
) -> dict[str, int]:
    imported = 0
    skipped = 0
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        for ho in handoffs:
            ho_id = uuid.uuid4().hex[:12]
            now = _now_iso()
            pid = project_id_override or ho.get("project_id")
            try:
                conn.execute(
                    "INSERT INTO handoffs(id, session_id, from_agent, project_id, project_path, "
                    "context, status, summary, open_questions, next_steps, created_at, expires_at) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ho_id,
                        ho.get("session_id", ""),
                        ho.get("from_agent", "import"),
                        pid,
                        ho.get("project_path"),
                        ho.get("context"),
                        "imported",
                        ho.get("summary", ""),
                        json.dumps(ho.get("open_questions") or []),
                        json.dumps(ho.get("next_steps") or []),
                        now,
                        None,
                    ),
                )
            except Exception:
                skipped += 1
                continue
            audit_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO audit_log(id, action, target_type, target_id, agent, details, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (audit_id, "import", "handoff", ho_id, None, f"original_id={ho.get('id')}", now),
            )
            imported += 1
        conn.commit()
    finally:
        conn.close()
    return {"imported": imported, "skipped": skipped}
