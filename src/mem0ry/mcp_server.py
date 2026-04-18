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


# Lazy-loaded spaCy expander (shared across calls)
_expander = None


def _get_expander():
    global _expander
    if _expander is None:
        from .conversations.spacy_expand import SpacyConceptSearch

        config = MemoryConfig()
        _expander = SpacyConceptSearch(model_name=config.spacy_model)
    return _expander


@mcp.tool()
def save_memory(title: str, content: str, dt: str = "") -> str:
    """Save a single memory entry (fact, note, or message).

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
    """Save a full conversation with multiple messages.

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
    from .conversations.query_expansion import expand_query
    from .conversations.search import search as rg_search

    conv_dir = _conversations_dir()
    if not conv_dir.exists():
        return []

    config = MemoryConfig()

    # Expand query with spaCy
    expander = _get_expander()
    effective_query = expand_query(query, expander, top_k=config.expand_top_k)

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
    file_path = conv_dir / path

    if not file_path.exists():
        return f"File not found: {path}"

    # Prevent path traversal
    try:
        file_path.resolve().relative_to(conv_dir.resolve())
    except ValueError:
        return "Invalid path"

    return file_path.read_text(encoding="utf-8")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
