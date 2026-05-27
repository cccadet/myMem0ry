"""Payload sanitization for lifecycle hook events."""

from __future__ import annotations

import re
from typing import Any

_MAX_BODY = 10_000
_MAX_TITLE = 500
_KEY_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"key[\s:=]+[\w\-]{16,}", re.IGNORECASE),
    re.compile(r"token[\s:=]+[\w\-\.]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[\w\-\.]{16,}"),
    re.compile(r'api[_-]?key["\s:=]+[\w\-]{16,}', re.IGNORECASE),
]
_HOME_PATTERN = re.compile(r"/(?:home|Users)/[^/\s]+")
_VALID_KINDS = {
    "session-start",
    "user-prompt",
    "post-tool-use",
    "pre-compact",
    "session-end",
    "log",
    "other",
}


def _strip_secrets(text: str) -> str:
    for pat in _KEY_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def _strip_home_paths(text: str) -> str:
    return _HOME_PATTERN.sub("~", text)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _sanitize_message(msg: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": str(msg.get("role", "user")),
        "content": _strip_secrets(_strip_home_paths(str(msg.get("content", "")))),
    }


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize and validate a hook payload.

    Returns a cleaned dict or raises ValueError for invalid input.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"Payload must be a dict, got {type(payload).__name__}")

    kind = str(payload.get("kind", "other"))
    if kind not in _VALID_KINDS:
        kind = "other"

    session_id = str(payload.get("session_id", ""))[:64] or None
    if not session_id:
        raise ValueError("session_id is required")

    agent = str(payload.get("agent", ""))[:64] or None
    cwd = str(payload.get("cwd", ""))[:512] or None
    project_id = str(payload.get("project_id", ""))[:256] or None

    title = payload.get("title")
    if title is not None:
        title = _strip_secrets(_strip_home_paths(str(title)))
        title = _truncate(title, _MAX_TITLE)

    body = payload.get("body")
    if body is not None:
        body = _strip_secrets(_strip_home_paths(str(body)))
        body = _truncate(body, _MAX_BODY)

    messages = payload.get("messages")
    if messages is not None and isinstance(messages, list):
        messages = [_sanitize_message(m) for m in messages]

    return {
        "kind": kind,
        "session_id": session_id,
        "agent": agent,
        "cwd": cwd,
        "project_id": project_id,
        "title": title,
        "body": body,
        "messages": messages,
    }
