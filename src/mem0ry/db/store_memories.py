from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema
from ._helpers import _now_iso
from .store_audit import record_audit

_VALID_SCOPES = {"global", "project", "context", "session"}
_VALID_SOURCES = {"claude-code", "opencode", "codex", "manual", "import", "hook"}
_VALID_MEMORY_TYPES = {"fact", "decision", "pattern", "log"}

_SCOPE_PRIORITY = ["session", "context", "project", "global"]


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

    if context:
        params = [context]
        sql = "SELECT * FROM memories WHERE scope = 'context' AND context = ?"
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        queries.append((sql + " ORDER BY created_at DESC", params))

    if project_id:
        queries.append(
            (
                "SELECT * FROM memories WHERE scope = 'project' AND project_id = ? ORDER BY created_at DESC",
                [project_id],
            )
        )

    queries.append(
        (
            "SELECT * FROM memories WHERE scope = 'global' AND memory_type != 'log' ORDER BY created_at DESC",
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
    from .retention import forget_sweep

    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    soft = result.get("soft_deleted", [])
    return [str(m["id"]) for m in soft]
