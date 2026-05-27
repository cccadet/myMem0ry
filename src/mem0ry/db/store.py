"""CRUD operations for the memories database."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema


_VALID_SCOPES = {"global", "project", "context", "session"}
_VALID_SOURCES = {"claude-code", "opencode", "codex", "manual", "import"}
_VALID_MEMORY_TYPES = {"fact", "decision", "pattern", "log"}

_SCOPE_PRIORITY = ["session", "context", "project", "global"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_scope(scope: str) -> str:
    if scope not in _VALID_SCOPES:
        raise ValueError(
            f"Invalid scope '{scope}'. Expected one of: {', '.join(sorted(_VALID_SCOPES))}"
        )
    return scope


def _validate_source(source: str) -> str:
    if source not in _VALID_SOURCES:
        raise ValueError(
            f"Invalid source '{source}'. Expected one of: {', '.join(sorted(_VALID_SOURCES))}"
        )
    return source


def _validate_memory_type(memory_type: str) -> str:
    if memory_type not in _VALID_MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory_type '{memory_type}'. Expected one of: {', '.join(sorted(_VALID_MEMORY_TYPES))}"
        )
    return memory_type


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
    """Insert a new memory and return its id."""
    _validate_scope(scope)
    _validate_source(source)
    _validate_memory_type(memory_type)
    mem_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    tags_json = json.dumps(tags or [])

    from .retention import compute_salience

    salience = compute_salience(memory_type, now, 0, None)
    pinned = 1 if memory_type in ("fact", "decision") else 0

    conn = get_connection(db_path)
    init_schema(conn)
    conn.execute(
        "INSERT INTO memories(id, content, scope, project_id, project_path, context, "
        "session_id, memory_type, source, tags, title, created_at, file_path, "
        "access_count, last_accessed_at, salience, pinned) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (
            mem_id,
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
    conn.close()

    try:
        record_audit(
            db_path,
            action="create",
            target_type="memory",
            target_id=mem_id,
            details=f"type={memory_type} scope={scope}",
        )
    except Exception:
        pass

    return mem_id


def get_context(
    db_path: Path,
    project_id: str | None = None,
    context: str | None = None,
    session_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Aggregate memories from session > context > project > global scopes.

    Returns up to *top_k* results total, distributed across scopes.
    """
    conn = get_connection(db_path)
    init_schema(conn)

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    queries: list[tuple[str, list[Any]]] = []

    if session_id:
        queries.append(
            (
                "SELECT * FROM memories WHERE scope = 'session' AND session_id = ? ORDER BY created_at DESC",
                [session_id],
            )
        )

    if context and project_id:
        queries.append(
            (
                "SELECT * FROM memories WHERE scope = 'context' AND context = ? AND project_id = ? ORDER BY created_at DESC",
                [context, project_id],
            )
        )
    elif context:
        queries.append(
            (
                "SELECT * FROM memories WHERE scope = 'context' AND context = ? ORDER BY created_at DESC",
                [context],
            )
        )

    if project_id:
        queries.append(
            (
                "SELECT * FROM memories WHERE scope = 'project' AND project_id = ? ORDER BY created_at DESC",
                [project_id],
            )
        )

    queries.append(
        (
            "SELECT * FROM memories WHERE scope = 'global' ORDER BY created_at DESC",
            [],
        )
    )

    active_scopes = len(queries)
    per_scope = max(1, top_k // active_scopes) if active_scopes > 0 else top_k

    for sql, params in queries:
        if len(results) >= top_k:
            break
        rows = conn.execute(sql, params if params else ()).fetchmany(per_scope)
        for row in rows:
            d = dict(row)
            if d["id"] not in seen:
                seen.add(d["id"])
                results.append(d)

    conn.close()

    track_reads(db_path, [r["id"] for r in results[:top_k]])

    return results[:top_k]


def list_scopes(db_path: Path, project_id: str | None = None) -> list[dict[str, Any]]:
    """List scopes with memory counts."""
    conn = get_connection(db_path)
    init_schema(conn)

    if project_id:
        rows = conn.execute(
            "SELECT scope, count(*) as cnt FROM memories "
            "WHERE project_id = ? OR scope = 'global' "
            "GROUP BY scope ORDER BY scope",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT scope, count(*) as cnt FROM memories GROUP BY scope ORDER BY scope"
        ).fetchall()

    conn.close()
    return [{"scope": row["scope"], "count": row["cnt"]} for row in rows]


def stats(db_path: Path) -> dict[str, Any]:
    """Return overview stats of the memories database."""
    conn = get_connection(db_path)
    init_schema(conn)

    total = conn.execute("SELECT count(*) FROM memories").fetchone()[0]

    by_scope: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT scope, count(*) as cnt FROM memories GROUP BY scope"
    ):
        by_scope.append({"scope": row["scope"], "count": row["cnt"]})

    by_source: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT source, count(*) as cnt FROM memories GROUP BY source"
    ):
        by_source.append({"source": row["source"], "count": row["cnt"]})

    by_type: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT memory_type, count(*) as cnt FROM memories GROUP BY memory_type"
    ):
        by_type.append({"memory_type": row["memory_type"], "count": row["cnt"]})

    projects: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT project_id, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL GROUP BY project_id ORDER BY cnt DESC"
    ):
        projects.append({"project_id": row["project_id"], "count": row["cnt"]})

    top_reads: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT id, title, access_count, last_accessed_at FROM memories "
        "WHERE access_count > 0 ORDER BY access_count DESC LIMIT 10"
    ):
        top_reads.append(
            {
                "id": row["id"],
                "title": row["title"],
                "access_count": row["access_count"],
                "last_accessed_at": row["last_accessed_at"],
            }
        )

    total_reads = conn.execute(
        "SELECT COALESCE(SUM(access_count), 0) FROM memories"
    ).fetchone()[0]

    conn.close()
    return {
        "total": total,
        "total_reads": total_reads,
        "by_scope": by_scope,
        "by_source": by_source,
        "by_type": by_type,
        "projects": projects,
        "top_reads": top_reads,
    }


def end_session(db_path: Path, session_id: str, summary: str | None = None) -> bool:
    """Mark a session as completed by updating its memories.

    If *summary* is provided, creates a new memory with the session summary.
    Returns True if the session had any memories.
    """
    conn = get_connection(db_path)
    init_schema(conn)

    rows = conn.execute(
        "SELECT id FROM memories WHERE session_id = ?", (session_id,)
    ).fetchall()

    if not rows:
        conn.close()
        return False

    now = _now_iso()
    for row in rows:
        conn.execute(
            "UPDATE memories SET updated_at = ? WHERE id = ?", (now, row["id"])
        )
    conn.commit()
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
    except Exception:
        pass

    return True


def search_memories(
    db_path: Path,
    query: str | None = None,
    scope: str | None = None,
    project_id: str | None = None,
    context: str | None = None,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Search memories with optional filters."""
    conn = get_connection(db_path)
    init_schema(conn)

    conditions: list[str] = []
    params: list[Any] = []

    if scope:
        conditions.append("scope = ?")
        params.append(scope)

    if project_id:
        conditions.append("(project_id = ? OR scope = 'global')")
        params.append(project_id)

    if context:
        conditions.append("(context = ? OR scope IN ('project', 'global'))")
        params.append(context)

    if memory_type:
        conditions.append("memory_type = ?")
        params.append(memory_type)

    if tags:
        for tag in tags:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = [dict(row) for row in rows]
    track_reads(db_path, [r["id"] for r in results])

    return results


def list_projects(db_path: Path) -> list[dict[str, Any]]:
    """List all project IDs with memory counts."""
    conn = get_connection(db_path)
    init_schema(conn)

    rows = conn.execute(
        "SELECT project_id, project_path, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL GROUP BY project_id ORDER BY cnt DESC"
    ).fetchall()

    conn.close()
    return [
        {
            "project_id": row["project_id"],
            "project_path": row["project_path"],
            "count": row["cnt"],
        }
        for row in rows
    ]


def touch_memory(db_path: Path, memory_id: str) -> bool:
    """Increment access_count and update last_accessed_at for a memory."""
    conn = get_connection(db_path)
    init_schema(conn)

    now = _now_iso()
    cursor = conn.execute(
        "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
        (now, memory_id),
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def track_reads(db_path: Path, memory_ids: list[str]) -> None:
    """Batch-increment access_count and update last_accessed_at for multiple memories.

    Single transaction, one UPDATE per id (indexed by PK). Fast for typical
    result sets of 5–50 memories.
    """
    if not memory_ids:
        return
    conn = get_connection(db_path)
    init_schema(conn)
    now = _now_iso()
    for mid in memory_ids:
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
            (now, mid),
        )
    conn.commit()
    conn.close()


def decay_memories(
    db_path: Path, days_threshold: int = 90, dry_run: bool = False
) -> list[str]:
    """Soft-delete unpinned memories past their retention threshold.

    Delegates to forget_sweep for tier-aware retention. The *days_threshold*
    parameter is kept for backward compatibility but the real threshold is
    derived from memory_type (see retention.py).
    """
    from .retention import forget_sweep

    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    soft = result.get("soft_deleted", [])
    return [str(m["id"]) for m in soft]


# ─── Observations ────────────────────────────────────────────────────────────


_VALID_KINDS = {
    "session-start",
    "user-prompt",
    "post-tool-use",
    "pre-compact",
    "session-end",
    "other",
}


def create_observation(
    db_path: Path,
    session_id: str,
    kind: str,
    agent: str | None = None,
    cwd: str | None = None,
    project_id: str | None = None,
    title: str | None = None,
    body: str | None = None,
) -> str:
    """Insert an immutable observation and return its id."""
    if kind not in _VALID_KINDS:
        kind = "other"
    obs_id = uuid.uuid4().hex[:12]
    now = _now_iso()

    conn = get_connection(db_path)
    init_schema(conn)
    conn.execute(
        "INSERT INTO observations(id, session_id, kind, agent, cwd, "
        "project_id, title, body, created_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (obs_id, session_id, kind, agent, cwd, project_id, title, body, now),
    )
    conn.commit()
    conn.close()

    try:
        record_audit(
            db_path,
            action="create_observation",
            target_type="observation",
            target_id=obs_id,
            agent=agent,
            details=f"kind={kind}",
        )
    except Exception:
        pass

    return obs_id


def get_session_observations(
    db_path: Path,
    session_id: str,
    kind: str | None = None,
    top_k: int = 100,
) -> list[dict[str, Any]]:
    """Return observations for a session, newest first."""
    conn = get_connection(db_path)
    init_schema(conn)

    if kind:
        rows = conn.execute(
            "SELECT * FROM observations WHERE session_id = ? AND kind = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (session_id, kind, top_k),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM observations WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (session_id, top_k),
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


# ─── Handoffs ────────────────────────────────────────────────────────────────


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
    """Create a handoff for the next agent. Returns handoff id."""
    ho_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    from datetime import timedelta

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
    """Fetch + ack the latest open handoff matching project_id.

    Marks it as accepted. Returns the handoff dict or None.
    """
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
    """Return the latest open handoff for project_id without accepting it."""
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
    """Create a rule-based handoff from session observations.

    Only creates if no open handoff already exists for this session.
    Returns handoff id or None.
    """
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
    """Mark expired handoffs as status='expired'."""
    now = _now_iso()
    conn.execute(
        "UPDATE handoffs SET status = 'expired' "
        "WHERE status = 'open' AND expires_at IS NOT NULL AND expires_at < ?",
        (now,),
    )
    conn.commit()


# ─── Audit Log ───────────────────────────────────────────────────────────────


def record_audit(
    db_path: Path,
    action: str,
    target_type: str,
    target_id: str,
    agent: str | None = None,
    details: str | None = None,
) -> str:
    """Record an audit log entry. Returns audit id."""
    audit_id = uuid.uuid4().hex[:12]
    now = _now_iso()

    conn = get_connection(db_path)
    init_schema(conn)
    conn.execute(
        "INSERT INTO audit_log(id, action, target_type, target_id, agent, details, created_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?)",
        (audit_id, action, target_type, target_id, agent, details, now),
    )
    conn.commit()
    conn.close()
    return audit_id


def query_audit_log(
    db_path: Path,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    top_k: int = 100,
) -> list[dict[str, Any]]:
    """Query audit log with optional filters."""
    conn = get_connection(db_path)
    init_schema(conn)

    conditions: list[str] = []
    params: list[Any] = []

    if action:
        conditions.append("action = ?")
        params.append(action)
    if target_type:
        conditions.append("target_type = ?")
        params.append(target_type)
    if target_id:
        conditions.append("target_id = ?")
        params.append(target_id)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM audit_log WHERE {where} ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]
