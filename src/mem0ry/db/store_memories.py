from __future__ import annotations

import json
import re
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

# Stop words (EN + PT) filtered from free-text queries so a natural-language
# question doesn't match every row on common glue words.
_STOP_WORDS = frozenset(
    "a an the of to in on at for and or but is are was were be been being this "
    "that these those it its as by with from "
    "o a os as um uma de do da dos das em no na nos nas e ou que para por com "
    "como qual quais onde quando".split()
)


def _query_terms(query: str | None) -> list[str]:
    """Extract meaningful search terms from a free-text query."""
    if not query:
        return []
    words = re.findall(r"[\wáàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]+", query.lower())
    return [w for w in words if len(w) > 1 and w not in _STOP_WORDS]


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
    try:
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
    # Scope priority: the most "local" context comes first (session work, then
    # the branch, then the project, then global knowledge). Within each scope,
    # pinned + high-salience + recent rows win. No per-scope cap — we fill the
    # top_k budget in priority order so a scope with many strong memories isn't
    # throttled to a single row.
    _ORDER = "ORDER BY pinned DESC, salience DESC, created_at DESC"

    conn = get_connection(db_path)
    try:
        init_schema(conn)

        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        queries: list[tuple[str, list[Any]]] = []

        if session_id:
            queries.append(
                (
                    f"SELECT * FROM memories WHERE scope = 'session' AND session_id = ? "
                    f"AND deleted_at IS NULL {_ORDER}",
                    [session_id],
                )
            )

        if context:
            params = [context]
            sql = (
                "SELECT * FROM memories WHERE scope = 'context' AND context = ? "
                "AND deleted_at IS NULL"
            )
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            queries.append((f"{sql} {_ORDER}", params))

        if project_id:
            queries.append(
                (
                    f"SELECT * FROM memories WHERE scope = 'project' AND project_id = ? "
                    f"AND deleted_at IS NULL {_ORDER}",
                    [project_id],
                )
            )

        queries.append(
            (
                f"SELECT * FROM memories WHERE scope = 'global' AND memory_type != 'log' "
                f"AND deleted_at IS NULL {_ORDER}",
                [],
            )
        )

        for sql, params in queries:
            if len(results) >= top_k:
                break
            remaining = top_k - len(results)
            rows = conn.execute(sql, params if params else ()).fetchmany(remaining)
            for row in rows:
                d = dict(row)
                if d["id"] not in seen:
                    seen.add(d["id"])
                    results.append(d)
    finally:
        conn.close()

    track_reads(db_path, [r["id"] for r in results[:top_k]])

    return results[:top_k]


def list_scopes(db_path: Path, project_id: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
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
    finally:
        conn.close()
    return [{"scope": row["scope"], "count": row["cnt"]} for row in rows]


def stats(db_path: Path) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
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
    finally:
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
    try:
        init_schema(conn)

        conditions: list[str] = ["deleted_at IS NULL"]
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

        # Free-text: every term must appear in content or title (AND of ORs),
        # so the result set narrows as the query gets more specific.
        for term in _query_terms(query):
            conditions.append("(content LIKE ? OR title LIKE ?)")
            like = f"%{term}%"
            params.extend([like, like])

        where = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM memories WHERE {where} "
            "ORDER BY pinned DESC, salience DESC, created_at DESC LIMIT ?"
        )
        params.append(top_k)

        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    results = [dict(row) for row in rows]
    track_reads(db_path, [r["id"] for r in results])

    return results


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
    track_reads(db_path, [memory_id])
    return dict(row)


def list_projects(db_path: Path) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        rows = conn.execute(
            "SELECT project_id, project_path, count(*) as cnt FROM memories "
            "WHERE project_id IS NOT NULL GROUP BY project_id ORDER BY cnt DESC"
        ).fetchall()
    finally:
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
    except Exception:
        pass
    finally:
        conn.close()


def track_reads(db_path: Path, memory_ids: list[str]) -> None:
    if not memory_ids:
        return
    import threading
    threading.Thread(target=_track_reads_sync, args=(db_path, memory_ids), daemon=True).start()


def delete_memory(db_path: Path, memory_id: str) -> bool:
    conn = get_connection(db_path)
    init_schema(conn)
    now = _now_iso()
    cursor = conn.execute(
        "UPDATE memories SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
        (now, memory_id),
    )
    conn.commit()
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
        except Exception:
            pass

    return affected > 0


def decay_memories(
    db_path: Path, dry_run: bool = False
) -> list[str]:
    from .retention import forget_sweep

    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    soft = result.get("soft_deleted", [])
    return [str(m["id"]) for m in soft]
