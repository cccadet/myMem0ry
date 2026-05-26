"""MCP server for myMem0ry — scoped memory system with session/context/project/global context."""

from __future__ import annotations

import os
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import MemoryConfig
from .conversations.spacy_expand import SpacyConceptSearch
from .utils.filenames import sanitize_title
from .utils.git_context import resolve_full_context

mcp = FastMCP("myMem0ry")

_PREVIEW_LINES = 5
_PREVIEW_MAX_CHARS = 500
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_session_id: str | None = None
_session_title: str = "session"
_expander: SpacyConceptSearch | None = None


def _validate_date(dt: str) -> str:
    if not _DATE_RE.match(dt):
        raise ValueError(f"Invalid date format: '{dt}'. Expected YYYY-MM-DD.")
    return dt


def _resolve_within(base: Path, *parts: str) -> Path:
    resolved = base.joinpath(*parts).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal blocked: '{'/'.join(parts)}' escapes base directory '{base}'"
        )
    return resolved


def _conversations_dir() -> Path:
    config = MemoryConfig()
    return Path(config.conversations_dir)


def _db_path() -> Path:
    config = MemoryConfig()
    return Path(config.db_path)


def _write_md(base: Path, date_str: str, title: str, content: str) -> Path:
    """Write a .md file in the standard myMem0ry format. Returns the resolved path."""
    file_id = uuid.uuid4().hex[:12]
    safe_date = os.path.basename(date_str)
    dir_path = base / safe_date
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.md"
    lines = [
        f"# {title}",
        f"> id: {file_id} | date: {date_str}",
        "",
        content,
    ]
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


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


def _get_expander() -> SpacyConceptSearch:
    global _expander
    if _expander is None:
        config = MemoryConfig()
        _expander = SpacyConceptSearch(model_name=config.spacy_model)
    return _expander


def _auto_session_id() -> str:
    """Generate a session ID from timestamp."""
    global _session_id
    if _session_id is None:
        _session_id = uuid.uuid4().hex[:8]
    return _session_id


def _resolve_cwd(cwd: str | None) -> dict[str, Any]:
    """Resolve full git context from cwd string."""
    if cwd:
        return resolve_full_context(Path(cwd), session_id=_auto_session_id())
    return {
        "project_id": None,
        "project_path": None,
        "context": None,
        "session_id": _auto_session_id(),
    }


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def log_message(role: str, content: str, cwd: str = "") -> str:
    """MANDATORY: Log a single message to the current conversation session.

    You MUST call this tool after EVERY message exchange — once for the
    user's message (role="user") and once for your response (role="assistant").

    Args:
        role: Who sent the message — "user" or "assistant".
        content: The message text.
        cwd: Current working directory (used for context resolution).
    """
    global _session_id, _session_title

    conv_dir = _conversations_dir()
    today = date.today().isoformat()
    dir_path = conv_dir / today
    dir_path.mkdir(parents=True, exist_ok=True)

    sid = _auto_session_id()
    safe_title = sanitize_title(_session_title)
    filename = f"{safe_title}-{sid}.md"
    file_path = dir_path / filename

    if not file_path.exists():
        header = f"# {safe_title}\n> id: {sid} | date: {today}\n\n"
        file_path.write_text(header, encoding="utf-8")

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{role}]: {content}\n\n")

    rel = file_path.relative_to(conv_dir)
    return f"Logged ({role}) to {rel}"


@mcp.tool()
def save_memory(
    title: str,
    content: str,
    scope: str = "global",
    memory_type: str = "log",
    cwd: str = "",
    project_id: str | None = None,
    context: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    source: str = "manual",
    dt: str = "",
) -> str:
    """CRITICAL: Save a single memory entry (fact, note, or decision).

    IMPORTANT: You MUST call this tool to save any important information
    discussed in this conversation. Proactively save relevant facts,
    decisions, and insights as they arise.

    Args:
        title: Title for the memory.
        content: Text content of the memory.
        scope: Memory scope — "global", "project", "context", or "session". Defaults to "global".
        memory_type: Type of memory — "fact", "decision", "pattern", or "log". Defaults to "log".
        cwd: Current working directory. Used to auto-resolve project_id and context.
        project_id: Override project identifier (e.g. git remote URL).
        context: Override context (e.g. git branch name).
        session_id: Session identifier (auto-generated if not provided).
        tags: Optional list of tags (e.g. ["auth", "decision"]).
        source: Where the memory came from — "claude-code", "opencode", "codex", "manual", "import".
        dt: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    from .db.store import create_memory

    resolved = _resolve_cwd(cwd)

    mem_date = _validate_date(dt) if dt else date.today().isoformat()

    mem_id = create_memory(
        db_path=_db_path(),
        content=content,
        scope=scope,
        project_id=project_id or resolved["project_id"],
        project_path=resolved["project_path"],
        context=context or resolved["context"],
        session_id=session_id or (resolved["session_id"] if scope == "session" else None),
        memory_type=memory_type,
        source=source,
        tags=tags,
        title=title,
    )

    conv_dir = _conversations_dir()
    file_path = _write_md(conv_dir, mem_date, title, content)

    rel = file_path.relative_to(conv_dir)
    return f"Saved: {rel} (id={mem_id}, scope={scope}, type={memory_type})"


@mcp.tool()
def save_conversation(title: str, messages: list[dict[str, str]], dt: str = "") -> str:
    """CRITICAL: Save a full conversation with multiple messages.

    MANDATORY: You MUST call this tool at the END of every conversation to
    archive the full exchange.

    Args:
        title: Title for the conversation.
        messages: List of {role, content} dicts.
        dt: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    conv_dir = _conversations_dir()
    mem_date = _validate_date(dt) if dt else date.today().isoformat()

    file_id = uuid.uuid4().hex[:12]
    safe_date = os.path.basename(mem_date)
    dir_path = conv_dir / safe_date
    dir_path.mkdir(parents=True, exist_ok=True)
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

    file_path.write_text("\n".join(lines), encoding="utf-8")
    rel = file_path.relative_to(conv_dir)
    return f"Saved: {rel}"


@mcp.tool()
def get_context(
    cwd: str = "",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Get aggregated context from session > context > project > global memories.

    Call this at the START of every session to load relevant context.

    Args:
        cwd: Absolute path of the current working directory.
        top_k: Maximum number of memories to return. Defaults to 5.
    """
    from .db.store import get_context as _get_ctx

    db = _db_path()
    if not db.exists():
        return []

    resolved = _resolve_cwd(cwd)

    return _get_ctx(
        db,
        project_id=resolved["project_id"],
        context=resolved["context"],
        session_id=resolved["session_id"],
        top_k=top_k,
    )


@mcp.tool()
def list_scopes(cwd: str = "") -> list[dict[str, Any]]:
    """List memory scopes with counts.

    Args:
        cwd: Current working directory (used to filter by project).
    """
    from .db.store import list_scopes as _list_scopes

    db = _db_path()
    if not db.exists():
        return []

    resolved = _resolve_cwd(cwd)
    return _list_scopes(db, project_id=resolved["project_id"])


@mcp.tool()
def end_session(session_id: str | None = None, summary: str | None = None) -> str:
    """Mark a session as completed. Optionally save a summary.

    Args:
        session_id: Session ID to end. Defaults to current session.
        summary: Optional text summary of what was accomplished.
    """
    from .db.store import end_session as _end_session

    global _session_id

    sid = session_id or _session_id
    if not sid:
        return "No active session to end."

    found = _end_session(_db_path(), sid, summary=summary)
    if not found:
        return f"No memories found for session {sid}."

    _session_id = None
    return f"Session {sid} ended." + (" Summary saved." if summary else "")


@mcp.tool()
def search_memory(
    query: str,
    top_k: int = 5,
    backend: str = "ripgrep",
    scope: str | None = None,
    cwd: str = "",
    memory_type: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search memories with semantic query expansion.

    Returns previews (path, title, first lines). Use read_memory to get full content.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results. Defaults to 5.
        backend: Search backend — "ripgrep", "bm25", "hybrid". Defaults to "ripgrep".
        scope: Optional scope filter — "global", "project", "context", "session".
        cwd: Current working directory (used for context resolution).
        memory_type: Optional memory type filter — "fact", "decision", "pattern", "log".
        tags: Optional list of tags to filter by.
    """
    from .conversations.spacy_expand import expand_query_spacy
    from .conversations.search import search as rg_search

    conv_dir = _conversations_dir()
    if not conv_dir.exists():
        return []

    config = MemoryConfig()
    expander = _get_expander()
    effective_query = expand_query_spacy(query, expander, top_k=config.expand_top_k)

    if backend == "hybrid":
        from .conversations.embeddings import SpacyEncoder
        from .conversations.search_hybrid import search_hybrid
        from .conversations.vector_store import VectorStore

        encoder = SpacyEncoder(model_name=config.spacy_model)
        vec_store = VectorStore(Path(config.vector_db_path), dim=config.embedding_dim)
        paths = search_hybrid(
            effective_query, conv_dir, encoder, vec_store,
            top_k=top_k, rrf_k=config.rrf_k,
        )
        vec_store.close()
    elif backend == "bm25":
        from .conversations.search_bm25 import search_bm25
        paths = search_bm25(effective_query, conv_dir, top_k=top_k)
    else:
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


@mcp.tool()
def memory_stats() -> dict[str, Any]:
    """Get overview statistics of the memories database.

    Returns total count, breakdown by scope, by source, by type, and by project.
    """
    from .db.store import stats as _stats

    db = _db_path()
    if not db.exists():
        return {"total": 0, "by_scope": [], "by_source": [], "by_type": [], "projects": []}

    return _stats(db)


@mcp.custom_route("/hook", methods=["POST"])
async def hook_endpoint(request: Any) -> Any:
    """Receive lifecycle hook events from agent CLIs.

    Accepts JSON with: event, cwd, role, content, session_id.
    """
    from starlette.responses import JSONResponse

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    event = body.get("event", "")
    cwd = body.get("cwd", "")
    content = body.get("content", "")
    sid = body.get("session_id")

    if sid:
        global _session_id
        _session_id = sid

    if event in ("SessionStart", "session_start"):
        get_context(cwd=cwd)
    elif event in ("UserPromptSubmit", "user_prompt"):
        log_message(role="user", content=content, cwd=cwd)
    elif event in ("AssistantResponse", "assistant_response"):
        log_message(role="assistant", content=content, cwd=cwd)
    elif event in ("SessionEnd", "session_end"):
        end_session(session_id=sid, summary=content if content else None)
    elif event in ("PostToolUse", "tool_use"):
        log_message(role="system", content=f"[tool] {content}", cwd=cwd)

    return JSONResponse({"status": "ok", "event": event}, status_code=202)


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Any) -> Any:
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok", "version": "0.4.0"})


# ─── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def auto_save_instructions() -> str:
    """System instructions for scoped memory management.

    Use this prompt at the start of every conversation.
    """
    return (
        "MANDATORY BEHAVIOR — myMem0ry Scoped Memory Protocol:\n"
        "\n"
        "You are connected to the myMem0ry memory system. You MUST follow these rules:\n"
        "\n"
        "## Session Start\n"
        "1. Call get_context with the current working directory (cwd) to load relevant context.\n"
        "\n"
        "## During Session\n"
        "2. After EVERY exchange, call log_message(role='user'/'assistant', content='...', cwd=<cwd>).\n"
        "3. Save important facts with save_memory:\n"
        "   - Technical decisions → save_memory(scope='project', cwd=<cwd>)\n"
        "   - Branch-specific state → save_memory(scope='context', cwd=<cwd>)\n"
        "   - Session-specific state → save_memory(scope='session', cwd=<cwd>)\n"
        "   - Personal preferences/patterns → save_memory(scope='global')\n"
        "   - Use memory_type: 'fact', 'decision', 'pattern', or 'log'\n"
        "\n"
        "## Session End\n"
        "4. Call end_session with a brief summary of what was accomplished.\n"
        "\n"
        "## Scope Resolution\n"
        "Scopes are resolved automatically from cwd:\n"
        "- session → current session ID\n"
        "- context → current git branch/worktree\n"
        "- project → git remote URL (or cwd if no git)\n"
        "- global → no resolution needed\n"
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
    import os

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "49374"))

    if transport in ("sse", "streamable-http"):
        mcp.run(transport=transport, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
