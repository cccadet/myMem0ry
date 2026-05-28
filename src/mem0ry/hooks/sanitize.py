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


def _summarize_post_tool_use(payload: dict[str, Any]) -> str | None:
    body = payload.get("body")
    if body is None:
        return None
    tool_name = payload.get("tool_name", "unknown")
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response")
    parts: list[str] = [f"tool: {tool_name}"]
    if isinstance(tool_input, dict):
        fp = tool_input.get("file_path") or tool_input.get("filePath")
        if fp:
            parts.append(f"file: {fp}")
        cmd = tool_input.get("command")
        if cmd:
            parts.append(f"command: {cmd[:200]}")
        query_val = tool_input.get("query") or tool_input.get("search")
        if query_val:
            parts.append(f"query: {str(query_val)[:200]}")
    if isinstance(tool_response, dict):
        err = tool_response.get("error")
        if err:
            parts.append(f"error: {str(err)[:300]}")
        success = tool_response.get("success")
        if success is not None:
            parts.append(f"success: {success}")
    return _strip_secrets(_truncate("; ".join(parts), _MAX_BODY))


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize and validate a hook payload.

    Returns a cleaned dict or raises ValueError for invalid input.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"Payload must be a dict, got {type(payload).__name__}")

    kind = str(payload.get("kind", "other"))
    hook_event = str(payload.get("hook_event_name", ""))
    if kind == "other" and hook_event:
        mapping = {
            "SessionStart": "session-start",
            "UserPrompt": "user-prompt",
            "PostToolUse": "post-tool-use",
            "PreCompact": "pre-compact",
            "SessionEnd": "session-end",
        }
        kind = mapping.get(hook_event, "other")

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

    if kind == "post-tool-use":
        body = _summarize_post_tool_use(payload)
    else:
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
