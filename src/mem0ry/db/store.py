"""CRUD operations for the memories database."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema


_VALID_SCOPES = {"global", "project", "session"}
_VALID_SOURCES = {"claude-code", "opencode", "manual", "import"}


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


def create_memory(
    db_path: Path,
    content: str,
    scope: str = "global",
    project_path: str | None = None,
    session_id: str | None = None,
    source: str = "manual",
    tags: list[str] | None = None,
    title: str | None = None,
    file_path: str | None = None,
) -> str:
    """Insert a new memory and return its id."""
    _validate_scope(scope)
    _validate_source(source)
    mem_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    tags_json = json.dumps(tags or [])

    conn = get_connection(db_path)
    init_schema(conn)
    conn.execute(
        "INSERT INTO memories(id, content, scope, project_path, session_id, source, tags, title, created_at, file_path) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (mem_id, content, scope, project_path, session_id, source, tags_json, title, now, file_path),
    )
    conn.commit()
    conn.close()
    return mem_id


def get_context(
    db_path: Path,
    project_path: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Aggregate memories from session > project > global scopes.

    Returns up to *top_k* results total, distributed across scopes.
    """
    conn = get_connection(db_path)
    init_schema(conn)

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    scope_queries: list[tuple[str, list[Any]]] = [
        ("session", ["SELECT * FROM memories WHERE scope = 'session' ORDER BY created_at DESC"]),
        ("project", []),
        ("global", ["SELECT * FROM memories WHERE scope = 'global' ORDER BY created_at DESC"]),
    ]

    if project_path:
        scope_queries[1] = (
            "project",
            ["SELECT * FROM memories WHERE scope = 'project' AND project_path = ? ORDER BY created_at DESC", project_path],
        )

    per_scope = max(2, top_k // 3)

    for _, query_info in scope_queries:
        if len(results) >= top_k:
            break
        if not query_info:
            continue

        sql = query_info[0]
        params = query_info[1:]
        rows = conn.execute(sql, params if params else ()).fetchmany(per_scope)
        for row in rows:
            d = dict(row)
            if d["id"] not in seen:
                seen.add(d["id"])
                results.append(d)

    conn.close()
    return results[:top_k]


def list_scopes(db_path: Path, project_path: str | None = None) -> list[dict[str, Any]]:
    """List scopes with memory counts."""
    conn = get_connection(db_path)
    init_schema(conn)

    if project_path:
        rows = conn.execute(
            "SELECT scope, count(*) as cnt FROM memories "
            "WHERE project_path = ? OR scope = 'global' "
            "GROUP BY scope ORDER BY scope",
            (project_path,),
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
    for row in conn.execute("SELECT scope, count(*) as cnt FROM memories GROUP BY scope"):
        by_scope.append({"scope": row["scope"], "count": row["cnt"]})

    by_source: list[dict[str, Any]] = []
    for row in conn.execute("SELECT source, count(*) as cnt FROM memories GROUP BY source"):
        by_source.append({"source": row["source"], "count": row["cnt"]})

    projects: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT project_path, count(*) as cnt FROM memories "
        "WHERE project_path IS NOT NULL GROUP BY project_path ORDER BY cnt DESC"
    ):
        projects.append({"path": row["project_path"], "count": row["cnt"]})

    conn.close()
    return {"total": total, "by_scope": by_scope, "by_source": by_source, "projects": projects}


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
        )

    return True


def search_memories(
    db_path: Path,
    query: str | None = None,
    scope: str | None = None,
    project_path: str | None = None,
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

    if project_path:
        conditions.append("(project_path = ? OR scope = 'global')")
        params.append(project_path)

    if tags:
        for tag in tags:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_projects(db_path: Path) -> list[dict[str, Any]]:
    """List all project paths with memory counts."""
    conn = get_connection(db_path)
    init_schema(conn)

    rows = conn.execute(
        "SELECT project_path, count(*) as cnt FROM memories "
        "WHERE project_path IS NOT NULL GROUP BY project_path ORDER BY cnt DESC"
    ).fetchall()

    conn.close()
    return [{"path": row["project_path"], "count": row["cnt"]} for row in rows]
