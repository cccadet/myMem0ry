from __future__ import annotations

from pathlib import Path
from typing import Any

from .helpers import _NOT_SUPERSEDED
from ..connection import get_connection
from ..schema import init_schema
from .lifecycle import track_reads


_ORDER = "ORDER BY pinned DESC, salience DESC, created_at DESC"


def _context_queries(
    project_id: str | None,
    context: str | None,
    session_id: str | None,
) -> list[tuple[str, list[Any]]]:
    """Build scope-priority queries for context retrieval."""
    queries: list[tuple[str, list[Any]]] = []

    if session_id:
        queries.append(
            (
                f"SELECT * FROM memories WHERE scope = 'session' AND session_id = ? "  # nosec B608
                f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED} {_ORDER}",  # nosec B608
                [session_id],
            )
        )

    if context:
        params = [context]
        sql = (
            "SELECT * FROM memories WHERE scope = 'context' AND context = ? "
            f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED}"  # nosec B608
        )
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        queries.append((f"{sql} {_ORDER}", params))

    if project_id:
        queries.append(
            (
                f"SELECT * FROM memories WHERE scope = 'project' AND project_id = ? "  # nosec B608
                f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED} {_ORDER}",  # nosec B608
                [project_id],
            )
        )

    queries.append(
        (
            f"SELECT * FROM memories WHERE scope = 'global' AND memory_type != 'log' "  # nosec B608
            f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED} {_ORDER}",  # nosec B608
            [],
        )
    )

    return queries


def _collect_rows(
    conn: Any,
    queries: list[tuple[str, list[Any]]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Run queries in priority order until top_k unique rows are collected."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

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

    return results


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
    queries = _context_queries(project_id, context, session_id)

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        results = _collect_rows(conn, queries, top_k)
    finally:
        conn.close()

    track_reads(db_path, [r["id"] for r in results[:top_k]])

    return results[:top_k]
