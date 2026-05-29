"""MCP server for myMem0ry — scoped memory system with session/context/project/global context."""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import MemoryConfig
from .utils.git_context import resolve_full_context

logger = logging.getLogger(__name__)

_START_TIME: float = time.monotonic()

mcp = FastMCP("myMem0ry")

_PREVIEW_LINES = 5
_PREVIEW_MAX_CHARS = 500
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_session_id: str | None = None
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


def _get_expander():
    global _expander
    if _expander is None:
        from .conversations.spacy_expand import SpacyConceptSearch
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
    """Resolve full git context from cwd string. Falls back to os.getcwd()."""
    path = Path(cwd) if cwd else Path.cwd()
    return resolve_full_context(path, session_id=_auto_session_id())


# ─── Tools ────────────────────────────────────────────────────────────────────


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

    final_project_id = project_id or resolved["project_id"]
    if scope in ("project", "context") and final_project_id is None:
        logger.warning(
            "save_memory: scope=%s but project_id is None (cwd=%r, resolved=%r)",
            scope, cwd, resolved["project_id"],
        )

    mem_date = _validate_date(dt) if dt else date.today().isoformat()

    mem_id = create_memory(
        db_path=_db_path(),
        content=content,
        scope=scope,
        project_id=final_project_id,
        project_path=resolved["project_path"],
        context=context or resolved["context"],
        session_id=session_id
        or (resolved["session_id"] if scope == "session" else None),
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
            effective_query,
            conv_dir,
            encoder,
            vec_store,
            top_k=top_k,
            rrf_k=config.rrf_k,
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
def read_memory(path: str) -> dict[str, Any]:
    """Read the full content of a memory file returned by search_memory.

    search_memory returns previews only; call this with the `path` field from a
    result to fetch the complete text. Useful when an agent picking up a handoff
    needs the full record, not just the preview.

    Args:
        path: Path relative to the conversations directory (as returned by search_memory).
    """
    conv_dir = _conversations_dir()
    if not conv_dir.exists():
        raise ValueError("No conversations directory yet — nothing to read.")
    file_path = _resolve_within(conv_dir, *Path(path).parts)
    if not file_path.is_file():
        raise ValueError(f"Memory not found: '{path}'")
    return {
        "path": path,
        "title": file_path.stem,
        "content": file_path.read_text(encoding="utf-8"),
    }



@mcp.tool()
def memory_handoff_begin(
    summary: str,
    open_questions: list[str] | None = None,
    next_steps: list[str] | None = None,
    cwd: str = "",
) -> str:
    """Open a handoff for the next agent. Call at session end.

    Creates a typed handoff record that the next agent (any supported CLI)
    can pick up via memory_handoff_accept or the session-start hook.

    Args:
        summary: Brief summary of what was accomplished or where you left off.
        open_questions: List of open questions for the next agent.
        next_steps: List of concrete next steps.
        cwd: Current working directory (used to match project).
    """
    from .db.store import begin_handoff

    resolved = _resolve_cwd(cwd)
    ho_id = begin_handoff(
        _db_path(),
        session_id=resolved["session_id"],
        from_agent="mcp-client",
        summary=summary,
        project_id=resolved["project_id"],
        project_path=resolved["project_path"],
        context=resolved["context"],
        open_questions=open_questions,
        next_steps=next_steps,
    )
    return f"Handoff {ho_id} created. Next agent will see it on session start."


@mcp.tool()
def memory_handoff_accept(
    cwd: str = "",
) -> dict[str, Any] | None:
    """Fetch + ack the latest open handoff for this project.

    Called at session start to pick up where the previous agent left off.
    Returns the handoff dict with summary, open_questions, next_steps,
    or None if no pending handoff.

    Args:
        cwd: Current working directory (used to match project).
    """
    from .db.store import accept_handoff

    resolved = _resolve_cwd(cwd)
    return accept_handoff(
        _db_path(),
        project_id=resolved["project_id"],
        accepted_by="mcp-client",
    )


@mcp.tool()
def memory_pin(memory_id: str) -> str:
    """Pin a memory — exempt from retention decay.

    Pinned memories are never soft-deleted by forget-sweep.

    Args:
        memory_id: The memory ID to pin.
    """
    from .db.retention import pin_memory

    found = pin_memory(_db_path(), memory_id)
    if found:
        return f"Pinned {memory_id}"
    return f"Memory {memory_id} not found or already deleted"


@mcp.tool()
def memory_unpin(memory_id: str) -> str:
    """Unpin a memory — subject to retention decay again.

    Args:
        memory_id: The memory ID to unpin.
    """
    from .db.retention import unpin_memory

    found = unpin_memory(_db_path(), memory_id)
    if found:
        return f"Unpinned {memory_id}"
    return f"Memory {memory_id} not found"


@mcp.tool()
def memory_forget_sweep(execute: bool = False) -> dict[str, Any]:
    """Sweep stale memories: soft-delete low-salience + hard-delete expired grace.

    By default runs in preview (dry-run) mode. Pass execute=True to apply changes.

    Retention tiers are derived from memory_type:
    - log → working (90d max, salience decay)
    - pattern → procedural (365d max, frequency-based)
    - fact/decision → semantic (indefinite, auto-pinned)

    Args:
        execute: If True, apply changes. Default is dry-run preview.
    """
    from .db.retention import forget_sweep

    result: dict[str, Any] = forget_sweep(_db_path(), dry_run=not execute)
    return result


@mcp.tool()
def memory_stats() -> dict[str, Any]:
    """Get overview statistics of the memories database.

    Returns total count, breakdown by scope, by source, by type, and by project.
    """
    from .db.store import stats as _stats

    db = _db_path()
    if not db.exists():
        return {
            "total": 0,
            "by_scope": [],
            "by_source": [],
            "by_type": [],
            "projects": [],
        }

    return _stats(db)


def _can_import_version() -> bool:
    try:
        from importlib.metadata import version

        version("mymem0ry")
        return True
    except Exception:
        return False



# ─── HTTP Endpoints ───────────────────────────────────────────────────────────


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Any) -> Any:
    """Health check endpoint with extended diagnostics."""
    from starlette.responses import JSONResponse

    db = _db_path()
    uptime = time.monotonic() - _START_TIME

    resp: dict[str, Any] = {
        "status": "ok",
        "version": "0.7.0",
        "uptime_seconds": round(uptime, 1),
        "db_exists": db.exists(),
    }

    if db.exists():
        from .db.store import stats as _stats

        try:
            s = _stats(db)
            resp["total_memories"] = s["total"]
        except Exception:
            resp["db_error"] = True

    return JSONResponse(resp)


@mcp.custom_route("/hook", methods=["POST"])
async def hook_endpoint(request: Any) -> Any:
    """Fire-and-forget lifecycle hook ingestion.

    Accepts JSON with: kind, session_id, agent, cwd, body, title.
    For session-end: also accepts `messages` (list of {role, content}) to
    archive the full conversation without LLM token cost.
    For log: accepts `body` to create a session-scoped memory.
    Returns 202 Accepted immediately.
    """
    from starlette.responses import JSONResponse

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    if not isinstance(payload, dict) or not payload.get("session_id"):
        return JSONResponse({"error": "session_id required"}, status_code=400)

    import threading

    db = _db_path()

    def _process() -> None:
        try:
            from .hooks.router import handle_hook_event
            handle_hook_event(db, payload)
        except Exception:
            import traceback
            traceback.print_exc()

    threading.Thread(target=_process, daemon=True).start()
    return JSONResponse({"status": "accepted"}, status_code=202)


@mcp.custom_route("/handoff/accept", methods=["GET"])
async def handoff_accept_endpoint(request: Any) -> Any:
    """HTTP endpoint for hooks to fetch pending handoffs."""
    from starlette.responses import JSONResponse

    from .db.store import accept_handoff

    cwd = request.query_params.get("cwd", "")
    project_id = None
    if cwd:
        resolved = resolve_full_context(Path(cwd))
        project_id = resolved.get("project_id")

    ho = accept_handoff(
        _db_path(),
        project_id=project_id,
        accepted_by=request.query_params.get("agent", "hook"),
    )

    if not ho:
        return JSONResponse(None)

    return JSONResponse(ho)


# ─── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def auto_save_instructions() -> str:
    """System instructions for scoped memory management.

    Use this prompt at the start of every conversation.
    """
    return (
        "myMem0ry Memory Protocol (read-only tools + hook-based writes):\n"
        "\n"
        "## Session Start\n"
        "1. Call get_context(cwd=<cwd>) to load relevant memories.\n"
        "\n"
        "## During Session\n"
        "2. Save important info with save_memory:\n"
        "   - Decisions → save_memory(scope='project', cwd=<cwd>, memory_type='decision')\n"
        "   - Facts → save_memory(scope='global', memory_type='fact')\n"
        "   - Patterns → save_memory(scope='global', memory_type='pattern')\n"
        "\n"
        "## Session End\n"
        "3. Call memory_handoff_begin(summary='...', cwd=<cwd>) to hand off to next agent.\n"
        "   Conversation archiving is handled automatically by hooks (zero tokens).\n"
        "\n"
        "## Search\n"
        "4. Use search_memory(query='...', cwd=<cwd>) to find past memories.\n"
    )


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        from .daemon import ensure_server
        import threading
        threading.Thread(target=ensure_server, daemon=True).start()
        mcp.run(transport="stdio")
        return

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "49374"))
    config = MemoryConfig()

    if transport in ("sse", "streamable-http"):
        from .auth import AuthMiddleware, CORSMiddleware, parse_allowed_hosts
        from .daemon import ensure_server
        from .web import get_web_routes

        allowed = parse_allowed_hosts(config.allowed_hosts)

        app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()

        web_routes = get_web_routes()
        for route in web_routes:
            app.routes.append(route)

        if config.cors_origins:
            app.add_middleware(CORSMiddleware, origins=config.cors_origins)

        if config.auth_token or allowed:
            app.add_middleware(
                AuthMiddleware,
                auth_token=config.auth_token,
                allowed_hosts=allowed,
            )

        import uvicorn

        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
