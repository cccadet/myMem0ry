from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
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

_NOT_SUPERSEDED = "(superseded_by IS NULL OR superseded_by = '')"

_SCOPE_PRIORITY = ["session", "context", "project", "global"]

# Whitelisted ORDER BY clauses for search/listing. Keys are the only values a
# caller (e.g. the web UI) may pass for ``order_by``; the default preserves the
# historical "most relevant first" ordering used everywhere else.
_DEFAULT_ORDER_M = "m.pinned DESC, m.salience DESC, m.created_at DESC"
_ORDER_BY_M = {
    "recent": "m.created_at DESC",
    "oldest": "m.created_at ASC",
    "salience": "m.salience DESC, m.created_at DESC",
    "access": "m.access_count DESC, m.created_at DESC",
    "title": "m.title COLLATE NOCASE ASC, m.created_at DESC",
}

# Stop words (EN + PT) filtered from free-text queries so a natural-language
# question doesn't match every row on common glue words.
_STOP_WORDS = frozenset(
    "a an the of to in on at for and or but is are was were be been being this "
    "that these those it its as by with from "
    "o a os as um uma de do da dos das em no na nos nas e ou que para por com "
    "como qual quais onde quando".split()
)


_SUFFIXES_PT = frozenset(
    "acao cao mento acao acoes amente ismo ista iveis aveis "
    "ando endo indo aram eram iram asse esse isse ado edo ido "
    "aram erem irem aria eria iria".split()
)

_SUFFIXES_EN = frozenset(
    "ing tion sion ment ness ly ful less able ible ous ive "
    "ize ise ate ful ings tions sions ments nesses".split()
)

_ALL_SUFFIXES = _SUFFIXES_PT | _SUFFIXES_EN


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


def _stem_word(word: str) -> str:
    for suffix in _ALL_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _normalize(text: str) -> str:
    return _strip_accents(text.lower())


def _query_terms(query: str | None) -> list[str]:
    """Extract meaningful, normalized search terms from a free-text query."""
    if not query:
        return []
    words = re.findall(r"[\wáàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]+", query.lower())
    terms: list[str] = []
    for w in words:
        if len(w) <= 1 or w in _STOP_WORDS:
            continue
        terms.append(_normalize(w))
    return terms


def _query_terms_raw(query: str | None) -> list[str]:
    """Extract raw (un-normalized) terms for UI highlighting."""
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
                    f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED} {_ORDER}",
                    [session_id],
                )
            )

        if context:
            params = [context]
            sql = (
                "SELECT * FROM memories WHERE scope = 'context' AND context = ? "
                f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED}"
            )
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            queries.append((f"{sql} {_ORDER}", params))

        if project_id:
            queries.append(
                (
                    f"SELECT * FROM memories WHERE scope = 'project' AND project_id = ? "
                    f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED} {_ORDER}",
                    [project_id],
                )
            )

        queries.append(
            (
                f"SELECT * FROM memories WHERE scope = 'global' AND memory_type != 'log' "
                f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED} {_ORDER}",
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


def _has_fts(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT count(*) FROM memories_fts LIMIT 0")
        return True
    except Exception:
        return False


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
    conditions: list[str] = ["m.deleted_at IS NULL", "(m.superseded_by IS NULL OR m.superseded_by = '')"]
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


def search_memories(
    db_path: Path,
    query: str | None = None,
    scope: str | None = None,
    project_id: str | None = None,
    context: str | None = None,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    top_k: int = 10,
    source: str | None = None,
    pinned_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    order_by: str | None = None,
    offset: int = 0,
    expanded_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        conditions, params = _build_filter_conditions(
            scope, project_id, context, memory_type,
            tags, source, pinned_only, date_from, date_to,
        )
        terms = _query_terms(query)

        if expanded_terms:
            existing = set(terms)
            for et in expanded_terms:
                norm = _normalize(et)
                if norm not in existing and len(norm) > 1:
                    terms.append(norm)
                    existing.add(norm)

        if terms and _has_fts(conn):
            rows = _search_fts(conn, terms, conditions, params, top_k, offset)
        elif terms:
            rows = _search_like(conn, terms, conditions, params, order_by, top_k, offset)
        else:
            rows = _search_filtered(conn, conditions, params, order_by, top_k, offset)
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
    where = " AND ".join(conditions)
    sql = (
        "SELECT m.* FROM memories m "
        "JOIN memories_fts fts ON m.rowid = fts.rowid "
        f"WHERE fts.memories_fts MATCH ? AND {where} "
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
    where = " AND ".join(like_conditions)
    order = _ORDER_BY_M.get(order_by or "", _DEFAULT_ORDER_M)
    sql = (
        f"SELECT m.* FROM memories m WHERE {where} "
        f"ORDER BY {order} LIMIT ? OFFSET ?"
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
    where = " AND ".join(conditions)
    order = _ORDER_BY_M.get(order_by or "", _DEFAULT_ORDER_M)
    sql = (
        f"SELECT m.* FROM memories m WHERE {where} "
        f"ORDER BY {order} LIMIT ? OFFSET ?"
    )
    params.extend([top_k, max(offset, 0)])
    return conn.execute(sql, params).fetchall()


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


def update_memory(
    db_path: Path,
    memory_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Update an existing (non-deleted) memory's editable fields.

    Only ``title``, ``content`` and ``tags`` are user-editable from the web UI;
    everything else (scope, salience, lineage) is managed by the system.
    """
    sets: list[str] = []
    params: list[Any] = []
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if content is not None:
        sets.append("content = ?")
        params.append(content)
    if tags is not None:
        sets.append("tags = ?")
        params.append(json.dumps(tags))
    if not sets:
        return False

    now = _now_iso()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(memory_id)

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        cursor = conn.execute(
            f"UPDATE memories SET {', '.join(sets)} WHERE id = ? AND deleted_at IS NULL",
            params,
        )
        conn.commit()
        affected = cursor.rowcount
    finally:
        conn.close()

    if affected > 0:
        try:
            record_audit(
                db_path,
                action="update",
                target_type="memory",
                target_id=memory_id,
            )
        except Exception:
            pass

    return affected > 0


def list_deleted_memories(db_path: Path, top_k: int = 200) -> list[dict[str, Any]]:
    """List soft-deleted memories (the trash), most recently deleted first."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        rows = conn.execute(
            "SELECT * FROM memories WHERE deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC LIMIT ?",
            (top_k,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def restore_memory(db_path: Path, memory_id: str) -> bool:
    """Bring a soft-deleted memory back, clearing its grace period."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        cursor = conn.execute(
            "UPDATE memories SET deleted_at = NULL, grace_until = NULL "
            "WHERE id = ? AND deleted_at IS NOT NULL",
            (memory_id,),
        )
        conn.commit()
        affected = cursor.rowcount
    finally:
        conn.close()

    if affected > 0:
        try:
            record_audit(
                db_path,
                action="restore",
                target_type="memory",
                target_id=memory_id,
            )
        except Exception:
            pass

    return affected > 0


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


def delete_memories_batch(db_path: Path, memory_ids: list[str]) -> int:
    if not memory_ids:
        return 0
    from datetime import datetime, timedelta, timezone

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        now = _now_iso()
        grace = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()
        placeholders = ",".join("?" for _ in memory_ids)
        cursor = conn.execute(
            f"UPDATE memories SET deleted_at = ?, grace_until = ? "
            f"WHERE id IN ({placeholders}) AND deleted_at IS NULL",
            [now, grace] + memory_ids,
        )
        affected = cursor.rowcount
        for mid in memory_ids:
            audit_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO audit_log(id, action, target_type, target_id, agent, details, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (audit_id, "delete", "memory", mid, None, "batch", now),
            )
        conn.commit()
    finally:
        conn.close()
    return affected


_EXPORT_MEMORIES_COLUMNS = [
    "id", "title", "content", "scope", "project_id", "project_path",
    "context", "session_id", "memory_type", "source", "tags",
    "created_at", "pinned", "salience",
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
        where = " AND ".join(conditions)
        cols = ", ".join(_EXPORT_MEMORIES_COLUMNS)
        rows = conn.execute(
            f"SELECT {cols} FROM memories WHERE {where} "
            "ORDER BY pinned DESC, salience DESC, created_at DESC",
            params,
        ).fetchall()
    finally:
        conn.close()
    from ._helpers import _now_iso as _now

    return {
        "version": 1,
        "exported_at": _now(),
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

            from .retention import compute_salience

            mtype = mem.get("memory_type", "log")
            salience = compute_salience(mtype, now, 0, None)
            pinned = 1 if mtype in ("fact", "decision") else 0

            conn.execute(
                "INSERT INTO memories(id, content, scope, project_id, project_path, context, "
                "session_id, memory_type, source, tags, title, created_at, file_path, "
                "access_count, last_accessed_at, salience, pinned) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                (
                    new_id,
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


def decay_memories(
    db_path: Path, dry_run: bool = False
) -> list[str]:
    from .retention import forget_sweep

    result: dict[str, Any] = forget_sweep(db_path, dry_run=dry_run)
    soft = result.get("soft_deleted", [])
    return [str(m["id"]) for m in soft]


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
            f"SELECT id, scope, project_id, project_path, context, tags, title "
            f"FROM memories WHERE id IN ({placeholders}) "
            f"AND deleted_at IS NULL AND {_NOT_SUPERSEDED}",
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
            f"UPDATE memories SET superseded_by = ?, deleted_at = ? "
            f"WHERE id IN ({placeholders})",
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
    except Exception:
        pass

    return {
        "new_id": new_id,
        "superseded_count": len(old_ids),
        "old_ids": old_ids,
    }
