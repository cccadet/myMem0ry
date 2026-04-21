"""MCP server for myMem0ry — save and search personal memories."""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import MemoryConfig

mcp = FastMCP("myMem0ry")

_UNSAFE_FS_CHARS = re.compile(r'[/\\:*?"<>|\n\r]')
_PREVIEW_LINES = 5
_PREVIEW_MAX_CHARS = 500
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _resolve_within(base: Path, *parts: str) -> Path:
    resolved = base.joinpath(*parts).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        raise ValueError("Invalid path")
    return resolved


def _sanitize_title(text: str) -> str:
    """Strip characters illegal in filenames."""
    text = text.strip().replace("\n", " ")
    text = _UNSAFE_FS_CHARS.sub("", text)
    return text[:120] or "untitled"


def _conversations_dir() -> Path:
    config = MemoryConfig()
    return Path(config.conversations_dir)


def _write_md(path: Path, title: str, content: str, dt: str) -> None:
    """Write a .md file in the standard myMem0ry format."""
    lines = [
        f"# {title}",
        f"> id: {uuid.uuid4().hex[:12]} | date: {dt}",
        "",
        content,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _preview_text(path: Path) -> str:
    """Return first few lines of a file, truncated."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    preview = "\n".join(lines[:_PREVIEW_LINES])
    if len(preview) > _PREVIEW_MAX_CHARS:
        preview = preview[:_PREVIEW_MAX_CHARS] + "..."
    return preview


_session_id: str | None = None
_session_title: str = "session"

_expander = None


def _get_expander():
    global _expander
    if _expander is None:
        from .conversations.spacy_expand import SpacyConceptSearch

        config = MemoryConfig()
        _expander = SpacyConceptSearch(model_name=config.spacy_model)
    return _expander


@mcp.tool()
def log_message(role: str, content: str) -> str:
    """MANDATORY: Log a single message to the current conversation session.

    You MUST call this tool after EVERY message exchange — once for the
    user's message (role="user") and once for your response (role="assistant").
    Each call appends to the same session file. A new file is created per
    conversation automatically.

    Args:
        role: Who sent the message — "user" or "assistant".
        content: The message text.
    """
    global _session_id, _session_title

    conv_dir = _conversations_dir()
    today = date.today().isoformat()
    dir_path = conv_dir / today
    dir_path.mkdir(parents=True, exist_ok=True)

    if _session_id is None:
        _session_id = uuid.uuid4().hex[:8]

    safe_title = _sanitize_title(_session_title)
    filename = f"{safe_title}-{_session_id}.md"
    file_path = dir_path / filename

    if not file_path.exists():
        header = f"# {safe_title}\n> id: {_session_id} | date: {today}\n\n"
        file_path.write_text(header, encoding="utf-8")

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{role}]: {content}\n\n")

    rel = file_path.relative_to(conv_dir)
    return f"Logged ({role}) to {rel}"


@mcp.tool()
def save_memory(title: str, content: str, dt: str = "") -> str:
    """CRITICAL: Save a single memory entry (fact, note, or message).

    IMPORTANT: You MUST call this tool to save any important information
    discussed in this conversation. Do not wait for the user to ask —
    proactively save relevant facts, decisions, and insights as they arise.

    Args:
        title: Title for the memory (becomes the filename).
        content: Text content of the memory.
        dt: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    conv_dir = _conversations_dir()
    mem_date = dt or date.today().isoformat()
    safe_title = _sanitize_title(title)

    dir_path = conv_dir / mem_date
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_title}.md"
    file_path = dir_path / filename

    # Avoid overwriting
    counter = 1
    while file_path.exists():
        file_path = dir_path / f"{safe_title}-{counter}.md"
        counter += 1

    _write_md(file_path, title, content, mem_date)
    rel = file_path.relative_to(conv_dir)
    return f"Saved: {rel}"


@mcp.tool()
def save_conversation(title: str, messages: list[dict[str, str]], dt: str = "") -> str:
    """CRITICAL: Save a full conversation with multiple messages.

    MANDATORY: You MUST call this tool at the END of every conversation to
    archive the full exchange. Do NOT skip this step. Always save the
    complete conversation including all user messages and your responses.

    Args:
        title: Title for the conversation.
        messages: List of {role, content} dicts (e.g. role="user" or "assistant").
        dt: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    conv_dir = _conversations_dir()
    mem_date = dt or date.today().isoformat()
    safe_title = _sanitize_title(title)

    dir_path = conv_dir / mem_date
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_title}.md"
    file_path = dir_path / filename

    counter = 1
    while file_path.exists():
        file_path = dir_path / f"{safe_title}-{counter}.md"
        counter += 1

    # Format as standard myMem0ry conversation
    lines = [
        f"# {title}",
        f"> id: {uuid.uuid4().hex[:12]} | date: {mem_date}",
        "",
    ]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"[{role}]: {content}")
        lines.append("")

    file_path.write_text("\n".join(lines), encoding="utf-8")
    rel = file_path.relative_to(conv_dir)
    return f"Saved: {rel}"


@mcp.tool()
def search_memory(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search memories with semantic query expansion (spaCy + ripgrep).

    Returns previews (path, title, first lines). Use read_memory to get full content.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results. Defaults to 5.
    """
    from .conversations.spacy_expand import expand_query_spacy
    from .conversations.search import search as rg_search

    conv_dir = _conversations_dir()
    if not conv_dir.exists():
        return []

    config = MemoryConfig()

    expander = _get_expander()
    effective_query = expand_query_spacy(query, expander, top_k=config.expand_top_k)

    # Search with ripgrep
    paths = rg_search(effective_query, conv_dir, top_k=top_k)

    results: list[dict[str, Any]] = []
    for p in paths:
        rel = str(p.relative_to(conv_dir))
        title = p.stem
        preview = _preview_text(p)
        results.append({"path": rel, "title": title, "preview": preview})

    return results


@mcp.tool()
def read_memory(path: str) -> str:
    """Read the full content of a memory file.

    Args:
        path: Relative path returned by search_memory (e.g. "2026-04-17/test.md").
    """
    conv_dir = _conversations_dir()
    try:
        file_path = _resolve_within(conv_dir, path)
    except ValueError:
        return "Invalid path"

    if not file_path.exists():
        return f"File not found: {path}"

    return file_path.read_text(encoding="utf-8")


@mcp.prompt()
def auto_save_instructions() -> str:
    """System instructions that force automatic conversation saving.

    Use this prompt at the start of every conversation to ensure all
    exchanges are automatically archived.
    """
    return (
        "MANDATORY BEHAVIOR — myMem0ry Auto-Save Protocol:\n"
        "\n"
        "You are connected to the myMem0ry memory system. You MUST follow these rules:\n"
        "\n"
        "1. After EVERY user message, call log_message(role='user', content='<user message>').\n"
        "2. After EVERY response you give, call log_message(role='assistant', content='<your response>').\n"
        "3. This creates a running log of the entire conversation, appending to the same file.\n"
        "4. A new session file is created automatically — no need to manage session IDs.\n"
        "5. Optionally, call save_memory for specific facts/decisions worth bookmarking.\n"
        "\n"
        "NEVER skip calling log_message. It must be called for EVERY exchange.\n"
        "\n"
        "Example:\n"
        "  log_message(role='user', content='What is the capital of France?')\n"
        "  log_message(role='assistant', content='The capital of France is Paris.')\n"
        "\n"
        "These rules are NON-NEGOTIABLE."
    )


@mcp.prompt()
def conversation_logger(topic: str = "") -> str:
    """Log the current conversation to myMem0ry immediately.

    Args:
        topic: Brief topic/title for the conversation being logged.
    """
    instructions = (
        "Immediately log the conversation using log_message.\n"
        "Call log_message(role='user', content='...') for each user message\n"
        "and log_message(role='assistant', content='...') for each assistant response.\n"
        "Do not respond without calling log_message for every message."
    )
    if topic:
        instructions = f"Conversation topic: {topic}\n\n{instructions}"
    return instructions


def main():
    mcp.run()


if __name__ == "__main__":
    main()
