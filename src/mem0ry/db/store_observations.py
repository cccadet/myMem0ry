from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema
from ._helpers import _now_iso
from .store_audit import record_audit

_VALID_KINDS = {
    "session-start",
    "user-prompt",
    "post-tool-use",
    "pre-compact",
    "session-end",
    "log",
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
