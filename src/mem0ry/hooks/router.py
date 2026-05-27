"""Hook event router — sanitize, resolve context, persist observation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils.git_context import resolve_full_context
from .sanitize import sanitize_payload


def handle_hook_event(
    db_path: Path,
    raw_payload: dict[str, Any],
) -> str:
    """Process a raw hook payload: sanitize, resolve context, store.

    On session-end, auto-creates a handoff from session observations.
    Returns the observation id.
    """
    from ..db.store import auto_handoff_from_session, create_observation

    payload = sanitize_payload(raw_payload)

    project_id = payload.get("project_id")
    if not project_id and payload.get("cwd"):
        resolved = resolve_full_context(Path(payload["cwd"]))
        project_id = resolved.get("project_id")
    elif not project_id:
        resolved = {}
    else:
        resolved = {"project_id": project_id}

    obs_id = create_observation(
        db_path,
        session_id=payload["session_id"],
        kind=payload["kind"],
        agent=payload.get("agent"),
        cwd=payload.get("cwd"),
        project_id=project_id,
        title=payload.get("title"),
        body=payload.get("body"),
    )

    if payload["kind"] == "session-end":
        agent = payload.get("agent") or "unknown"
        auto_handoff_from_session(db_path, payload["session_id"], agent)

    return obs_id
