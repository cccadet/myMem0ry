from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema
from ._helpers import _now_iso


def record_audit(
    db_path: Path,
    action: str,
    target_type: str,
    target_id: str,
    agent: str | None = None,
    details: str | None = None,
) -> str:
    audit_id = uuid.uuid4().hex[:12]
    now = _now_iso()

    conn = get_connection(db_path)
    try:
        init_schema(conn)
        conn.execute(
            "INSERT INTO audit_log(id, action, target_type, target_id, agent, details, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (audit_id, action, target_type, target_id, agent, details, now),
        )
        conn.commit()
    finally:
        conn.close()
    return audit_id


def query_audit_log(
    db_path: Path,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    top_k: int = 100,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
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
    finally:
        conn.close()
    return [dict(row) for row in rows]
