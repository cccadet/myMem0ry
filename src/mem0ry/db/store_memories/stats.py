from __future__ import annotations

from pathlib import Path
from typing import Any

from ..connection import get_connection
from ..schema import init_schema


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
