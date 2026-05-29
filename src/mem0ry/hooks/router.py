"""Hook event router — sanitize, resolve context, persist observation.

Handles all write operations (logging, conversation archiving, session end)
so the MCP tools can stay read-only and avoid burning LLM tokens.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from ..config import MemoryConfig
from ..utils.git_context import resolve_full_context
from .sanitize import _sanitize_message, sanitize_payload


def _messages_from_transcript(transcript_path: str) -> list[dict[str, str]] | None:
    """Extract sanitized [{role, content}] from a Claude Code transcript JSONL.

    Lets session-end archive the full conversation with zero LLM tokens when the
    agent passes `transcript_path` instead of inlining `messages`. Returns None
    if the file is missing or unparseable, so archiving is simply skipped.
    """
    path = Path(transcript_path)
    if not path.is_file():
        return None
    try:
        from ..parsers.claude import ClaudeCodeParser

        convs = ClaudeCodeParser().parse(path)
    except Exception:
        return None
    if not convs:
        return None
    return [
        _sanitize_message({"role": m.role, "content": m.content})
        for m in convs[0].messages
    ]


def _write_conversation_md(
    title: str,
    messages: list[dict[str, str]],
    summary: str | None = None,
    dt: str | None = None,
) -> str:
    """Write a conversation to .md and return the relative path."""
    config = MemoryConfig()
    conv_dir = Path(config.conversations_dir)
    mem_date = dt or date.today().isoformat()
    safe_date = os.path.basename(mem_date)
    dir_path = conv_dir / safe_date
    dir_path.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:12]
    file_path = dir_path / f"{file_id}.md"

    lines = [
        f"# {title}",
        f"> id: {file_id} | date: {mem_date}",
        "",
    ]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"[{role}]: {content}")
        lines.append("")

    if summary:
        lines.append("## Summary")
        lines.append(summary)
        lines.append("")

    file_path.write_text("\n".join(lines), encoding="utf-8")
    return str(file_path.relative_to(conv_dir))


def handle_hook_event(
    db_path: Path,
    raw_payload: dict[str, Any],
) -> str:
    """Process a raw hook payload: sanitize, resolve context, store.

    Supported kinds:
      - session-start: observation only
      - user-prompt / post-tool-use / pre-compact: observation only
      - session-end: observation + conversation archive + auto-handoff
      - log: quick log (creates a session-scoped memory)

    On session-end, archives the conversation (hook-based, zero LLM tokens) from
    `messages` if present, otherwise from a `transcript_path` the server parses.

    Returns the observation id.
    """
    from ..db.store import auto_handoff_from_session, create_observation, end_session

    payload = sanitize_payload(raw_payload)
    kind = payload["kind"]

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
        kind=kind,
        agent=payload.get("agent"),
        cwd=payload.get("cwd"),
        project_id=project_id,
        title=payload.get("title"),
        body=payload.get("body"),
    )

    if kind == "log":
        from ..db.store import create_memory

        try:
            create_memory(
                db_path,
                content=payload.get("body") or payload.get("title") or "",
                scope="session",
                session_id=payload["session_id"],
                project_id=project_id,
                project_path=payload.get("cwd"),
                memory_type="log",
                source="hook",
                title=payload.get("title") or "log",
            )
        except Exception:
            pass

    if kind == "session-end":
        messages = payload.get("messages")
        if not messages and payload.get("transcript_path"):
            messages = _messages_from_transcript(payload["transcript_path"])
        if messages and isinstance(messages, list):
            title = payload.get("title") or f"Session {payload['session_id']}"
            summary = payload.get("body")
            try:
                _write_conversation_md(
                    title=title,
                    messages=messages,
                    summary=summary,
                )
            except Exception:
                pass

        try:
            end_session(db_path, payload["session_id"], summary=payload.get("body"))
        except Exception:
            pass

        try:
            agent = payload.get("agent") or "unknown"
            auto_handoff_from_session(db_path, payload["session_id"], agent)
        except Exception:
            pass

    return obs_id
