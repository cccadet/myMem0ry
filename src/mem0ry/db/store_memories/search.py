from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, TypedDict, Unpack

from ..connection import get_connection
from ..schema import init_schema
from .helpers import (
    _DEFAULT_ORDER_M,
    _JOIN_AND,
    _NOT_DELETED_M,
    _NOT_SUPERSEDED_M,
    _ORDER_BY_M,
    _normalize,
    _query_terms,
)
from .lifecycle import track_reads


def _has_fts(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT count(*) FROM memories_fts LIMIT 0")
        return True
    except Exception:
        return False


class _SearchFilters(TypedDict, total=False):
    scope: str | None
    project_id: str | None
    context: str | None
    memory_type: str | None
    tags: list[str] | None
    source: str | None
    pinned_only: bool
    date_from: str | None
    date_to: str | None


def _build_filter_conditions(
    scope: str | None,
    project_id: str | None,
    context: str | None,
    memory_type: str | None,
    tags: list[str] | None,
    source: str | None,
    pinned_only: bool,
    date_from: str | None,
    date_to: str | None,
) -> tuple[list[str], list[Any]]:
    conditions: list[str] = [_NOT_DELETED_M, _NOT_SUPERSEDED_M]
    params: list[Any] = []

    if scope:
        conditions.append("m.scope = ?")
        params.append(scope)

    if source:
        conditions.append("m.source = ?")
        params.append(source)

    if pinned_only:
        conditions.append("m.pinned = 1")

    if date_from:
        conditions.append("m.created_at >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("m.created_at < ?")
        params.append(date_to + "T99")

    if project_id:
        conditions.append("(m.project_id = ? OR m.scope = 'global')")
        params.append(project_id)

    if context:
        conditions.append("(m.context = ? OR m.scope IN ('project', 'global'))")
        params.append(context)

    if memory_type:
        conditions.append("m.memory_type = ?")
        params.append(memory_type)

    if tags:
        for tag in tags:
            conditions.append("m.tags LIKE ?")
            params.append(f'%"{tag}"%')

    return conditions, params


def _merge_terms(query: str | None, expanded_terms: list[str] | None) -> list[str]:
    """Normalize query terms and merge in optional expanded synonyms."""
    terms = _query_terms(query)
    if not expanded_terms:
        return terms

    existing = set(terms)
    for et in expanded_terms:
        norm = _normalize(et)
        if norm not in existing and len(norm) > 1:
            terms.append(norm)
            existing.add(norm)
    return terms


def _execute_search(
    conn: sqlite3.Connection,
    terms: list[str],
    conditions: list[str],
    params: list[Any],
    order_by: str | None,
    top_k: int,
    offset: int,
) -> list[Any]:
    """Pick FTS, LIKE or filtered search based on terms and index availability."""
    if terms and _has_fts(conn):
        return _search_fts(conn, terms, conditions, params, top_k, offset)
    if terms:
        return _search_like(conn, terms, conditions, params, order_by, top_k, offset)
    return _search_filtered(conn, conditions, params, order_by, top_k, offset)


def search_memories(
    db_path: Path,
    query: str | None = None,
    top_k: int = 10,
    order_by: str | None = None,
    offset: int = 0,
    expanded_terms: list[str] | None = None,
    **filters: Unpack[_SearchFilters],
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        conditions, params = _build_filter_conditions(
            filters.get("scope"),
            filters.get("project_id"),
            filters.get("context"),
            filters.get("memory_type"),
            filters.get("tags"),
            filters.get("source"),
            filters.get("pinned_only", False),
            filters.get("date_from"),
            filters.get("date_to"),
        )
        terms = _merge_terms(query, expanded_terms)
        rows = _execute_search(conn, terms, conditions, params, order_by, top_k, offset)
    finally:
        conn.close()

    results = [dict(row) for row in rows]
    track_reads(db_path, [r["id"] for r in results])

    return results


def _search_fts(
    conn: sqlite3.Connection,
    terms: list[str],
    conditions: list[str],
    params: list[Any],
    top_k: int,
    offset: int,
) -> list[Any]:
    fts_query = " OR ".join(f'"{t}"' for t in terms)
    where = _JOIN_AND.join(conditions)
    sql = (
        "SELECT m.* FROM memories m "
        "JOIN memories_fts fts ON m.fts_rowid = fts.rowid "
        f"WHERE fts.memories_fts MATCH ? AND {where} "  # nosec B608
        "ORDER BY fts.rank "
        "LIMIT ? OFFSET ?"
    )
    fts_params: list[Any] = [fts_query] + params + [top_k, max(offset, 0)]
    return conn.execute(sql, fts_params).fetchall()


def _search_like(
    conn: sqlite3.Connection,
    terms: list[str],
    conditions: list[str],
    params: list[Any],
    order_by: str | None,
    top_k: int,
    offset: int,
) -> list[Any]:
    like_conditions = list(conditions)
    like_params = list(params)
    for term in terms:
        like_conditions.append("(m.content LIKE ? OR m.title LIKE ?)")
        like = f"%{term}%"
        like_params.extend([like, like])
    where = _JOIN_AND.join(like_conditions)
    order = _ORDER_BY_M.get(order_by or "", _DEFAULT_ORDER_M)
    sql = (
        f"SELECT m.* FROM memories m WHERE {where} "  # nosec B608
        f"ORDER BY {order} LIMIT ? OFFSET ?"  # nosec B608
    )
    like_params.extend([top_k, max(offset, 0)])
    return conn.execute(sql, like_params).fetchall()


def _search_filtered(
    conn: sqlite3.Connection,
    conditions: list[str],
    params: list[Any],
    order_by: str | None,
    top_k: int,
    offset: int,
) -> list[Any]:
    where = _JOIN_AND.join(conditions)
    order = _ORDER_BY_M.get(order_by or "", _DEFAULT_ORDER_M)
    sql = (
        f"SELECT m.* FROM memories m WHERE {where} "  # nosec B608
        f"ORDER BY {order} LIMIT ? OFFSET ?"  # nosec B608
    )
    params.extend([top_k, max(offset, 0)])
    return conn.execute(sql, params).fetchall()
