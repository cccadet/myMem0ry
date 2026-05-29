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


def _memories_dir() -> Path:
    config = MemoryConfig()
    return Path(config.memories_dir)


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
    """Resolve full git context from cwd string. Falls back to os.getcwd().

    Uses the stable (never-None) project id for scoping so repos without a git
    remote don't all collapse onto a single `None` bucket.
    """
    path = Path(cwd) if cwd else Path.cwd()
    resolved = resolve_full_context(path, session_id=_auto_session_id())
    resolved["project_id"] = resolved["stable_project_id"]
    return resolved


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

    # Export a human-readable .md alongside the DB row. Curated memories live in
    # their own dir (not mixed with archived conversation dumps) so a general
    # conversation search never buries them.
    mem_dir = _memories_dir()
    file_path = _write_md(mem_dir, mem_date, title, content)
    rel = str(file_path.relative_to(mem_dir))

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
        file_path=rel,
    )

    return f"Saved id={mem_id} (scope={scope}, type={memory_type}). Pin with memory_pin('{mem_id}')."


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
    scope: str | None = None,
    cwd: str = "",
    memory_type: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search your CURATED memories (facts, decisions, patterns, logs).

    Scope-aware and metadata-rich: results are filtered to the current project +
    global by default, and respect the scope/memory_type/tags filters. Each result
    includes the `id` — pass it to memory_pin / read_memory.

    For free-form search across full archived CONVERSATIONS, use
    search_conversations instead.

    Args:
        query: Natural language search query (terms are matched against title + content).
        top_k: Maximum number of results. Defaults to 5.
        scope: Optional scope filter — "global", "project", "context", "session".
        cwd: Current working directory — scopes results to this project + global.
        memory_type: Optional memory type filter — "fact", "decision", "pattern", "log".
        tags: Optional list of tags to filter by.
    """
    from .db.store import search_memories

    db = _db_path()
    if not db.exists():
        return []

    resolved = _resolve_cwd(cwd)

    rows = search_memories(
        db,
        query=query,
        scope=scope,
        project_id=resolved["project_id"],
        context=resolved["context"],
        memory_type=memory_type,
        tags=tags,
        top_k=top_k,
    )

    results: list[dict[str, Any]] = []
    for r in rows:
        content = r.get("content") or ""
        preview = content[:_PREVIEW_MAX_CHARS]
        if len(content) > _PREVIEW_MAX_CHARS:
            preview += "..."
        results.append(
            {
                "id": r["id"],
                "title": r.get("title") or "",
                "scope": r.get("scope"),
                "memory_type": r.get("memory_type"),
                "preview": preview,
                "created_at": r.get("created_at"),
                "pinned": bool(r.get("pinned")),
            }
        )

    return results


@mcp.tool()
def search_conversations(
    query: str,
    top_k: int = 5,
    backend: str = "ripgrep",
) -> list[dict[str, Any]]:
    """General full-text/semantic search across archived CONVERSATIONS.

    This is the "broad sweep" over full session transcripts (saved at session end),
    not the curated-memory store. Returns previews with a `path`; pass it to
    read_memory to fetch the full transcript.

    Args:
        query: Natural language search query (expanded with semantically similar terms).
        top_k: Maximum number of results. Defaults to 5.
        backend: Search backend — "ripgrep", "bm25", "hybrid". Defaults to "ripgrep".
    """
    from .conversations.spacy_expand import expand_query_spacy
    from .conversations.search import search as rg_search

    conv_dir = _conversations_dir()
    if not conv_dir.exists():
        return []

    config = MemoryConfig()
    effective_query = query
    try:
        expander = _get_expander()
        effective_query = expand_query_spacy(query, expander, top_k=config.expand_top_k)
    except Exception:
        # spaCy model not installed / failed to load — degrade to raw query.
        logger.warning("query expansion unavailable; searching with raw query")

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
        results.append({"path": rel, "title": p.stem, "preview": _preview_text(p)})

    return results


def _looks_like_path(ref: str) -> bool:
    """A search_conversations result is a path; a search_memory result is an id."""
    return ref.endswith(".md") or "/" in ref or "\\" in ref


@mcp.tool()
def read_memory(ref: str) -> dict[str, Any]:
    """Read the full content of a search result.

    Accepts either:
    - a memory `id` (from search_memory) → returns the stored memory, or
    - a conversation `path` (from search_conversations) → returns the archived .md.

    Args:
        ref: A memory id or a conversation path (relative to the conversations dir).
    """
    if _looks_like_path(ref):
        conv_dir = _conversations_dir()
        if not conv_dir.exists():
            raise ValueError("No conversations directory yet — nothing to read.")
        file_path = _resolve_within(conv_dir, *Path(ref).parts)
        if not file_path.is_file():
            raise ValueError(f"Conversation not found: '{ref}'")
        return {
            "path": ref,
            "title": file_path.stem,
            "content": file_path.read_text(encoding="utf-8"),
        }

    from .db.store import get_memory_by_id

    mem = get_memory_by_id(_db_path(), ref)
    if not mem:
        raise ValueError(f"Memory not found: '{ref}'")
    return {
        "id": mem["id"],
        "title": mem.get("title") or "",
        "scope": mem.get("scope"),
        "memory_type": mem.get("memory_type"),
        "content": mem.get("content") or "",
    }



@mcp.tool()
def memory_handoff_begin(
    summary: str,
    open_questions: list[str] | None = None,
    next_steps: list[str] | None = None,
    cwd: str = "",
    from_agent: str = "mcp-client",
) -> str:
    """Open a handoff for the next agent. Call at session end.

    Creates a typed handoff record that the next agent (any supported CLI)
    can pick up via memory_handoff_accept or the session-start hook.

    Args:
        summary: Brief summary of what was accomplished or where you left off.
        open_questions: List of open questions for the next agent.
        next_steps: List of concrete next steps.
        cwd: Current working directory (used to match project).
        from_agent: Which harness/CLI is creating the handoff (e.g. "claude-code",
            "codex", "opencode"). Self-identify so the next agent knows the origin —
            this is what makes cross-harness handoff traceable. Defaults to "mcp-client".
    """
    from .db.store import begin_handoff

    resolved = _resolve_cwd(cwd)
    ho_id = begin_handoff(
        _db_path(),
        session_id=resolved["session_id"],
        from_agent=from_agent,
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
    """Peek at the latest open handoff for this project (non-destructive).

    The SessionStart hook already fetches and acknowledges the pending handoff and
    injects it into the first prompt, so you normally don't need this. Call it only
    to re-read the handoff mid-session — it does NOT consume/ack it, so the record
    stays available. Returns the handoff dict (summary, open_questions, next_steps)
    or None if there is no pending handoff.

    Args:
        cwd: Current working directory (used to match project).
    """
    from .db.store import pending_handoff

    resolved = _resolve_cwd(cwd)
    return pending_handoff(
        _db_path(),
        project_id=resolved["project_id"],
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

    result: dict[str, Any] = forget_sweep(
        _db_path(), dry_run=not execute, memories_dir=_memories_dir()
    )
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


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("mymem0ry")
    except Exception:
        return "unknown"



# ─── HTTP Endpoints ───────────────────────────────────────────────────────────


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Any) -> Any:
    """Health check endpoint with extended diagnostics."""
    from starlette.responses import JSONResponse

    db = _db_path()
    uptime = time.monotonic() - _START_TIME

    resp: dict[str, Any] = {
        "status": "ok",
        "version": _version(),
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
        from .utils.git_context import stable_project_id

        project_id = stable_project_id(Path(cwd))

    ho = accept_handoff(
        _db_path(),
        project_id=project_id,
        accepted_by=request.query_params.get("agent", "hook"),
    )

    if not ho:
        return JSONResponse(None)

    return JSONResponse(ho)


@mcp.custom_route("/context", methods=["GET"])
async def context_endpoint(request: Any) -> Any:
    """HTTP endpoint for the SessionStart hook to fetch starting context.

    Lets the hook inject relevant memories into the first prompt for free (no LLM
    tokens), the same way it injects the pending handoff.
    """
    from starlette.responses import JSONResponse

    from .db.store import get_context as _get_ctx
    from .utils.git_context import resolve_full_context, stable_project_id

    db = _db_path()
    if not db.exists():
        return JSONResponse([])

    cwd = request.query_params.get("cwd", "")
    try:
        top_k = int(request.query_params.get("top_k", "5"))
    except ValueError:
        top_k = 5

    if cwd:
        resolved = resolve_full_context(Path(cwd))
        project_id = stable_project_id(Path(cwd))
        context = resolved.get("context")
    else:
        project_id = None
        context = None

    rows = _get_ctx(db, project_id=project_id, context=context, top_k=top_k)
    return JSONResponse(
        [
            {
                "scope": r.get("scope"),
                "memory_type": r.get("memory_type"),
                "title": r.get("title") or "",
                "content": (r.get("content") or "")[:300],
            }
            for r in rows
        ]
    )


# ─── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def auto_save_instructions() -> str:
    """System instructions for scoped memory management.

    Use this prompt at the start of every conversation.
    """
    return (
        "myMem0ry Memory Protocol:\n"
        "\n"
        "## Session Start\n"
        "The SessionStart hook auto-injects the pending handoff and relevant context\n"
        "into your first prompt (zero tokens) — read it. Call get_context(cwd=<cwd>)\n"
        "only if you need more than what was injected.\n"
        "\n"
        "## During Session\n"
        "Save what's worth remembering with save_memory (returns an id):\n"
        "   - Decisions → save_memory(scope='project', cwd=<cwd>, memory_type='decision')\n"
        "   - Facts → save_memory(scope='global', memory_type='fact')\n"
        "   - Patterns → save_memory(scope='global', memory_type='pattern')\n"
        "Pin the important ones with memory_pin(<id>) so they survive retention.\n"
        "\n"
        "## Session End\n"
        "Call memory_handoff_begin(summary='...', cwd=<cwd>) to hand off to the next\n"
        "agent. Conversation archiving + a fallback handoff are automatic (zero tokens),\n"
        "but an explicit summary is always better.\n"
        "\n"
        "## Search\n"
        "   - search_memory(query='...', cwd=<cwd>) → your curated memories (scoped, has ids).\n"
        "   - search_conversations(query='...') → broad search across archived transcripts.\n"
        "   - read_memory(<id-or-path>) → full content of any result.\n"
    )


_SPOOL_POLL_SECONDS = 3.0


def _runtime_file() -> Path:
    """Fixed, env-independent location where the server advertises its spool dir so
    hooks can find it without re-deriving paths from env."""
    return Path.home() / ".mymem0ry" / "runtime"


def _write_runtime_file() -> None:
    # Plain text (line 1 = spool dir, line 2 = url) so the bash hook can read the
    # raw path with `read` — no JSON un-escaping of Windows backslashes needed.
    try:
        cfg = MemoryConfig()
        rt = _runtime_file()
        rt.parent.mkdir(parents=True, exist_ok=True)
        rt.write_text(
            f"{Path(cfg.spool_dir)}\nhttp://{cfg.server_host}:{cfg.server_port}\n",
            encoding="utf-8",
            newline="\n",  # no CRLF — the bash hook reads line 1 raw
        )
    except Exception:
        pass


def _drain_spool_once() -> int:
    """Process and delete every spooled lifecycle event. Returns the count handled.

    The SessionEnd hook can't reliably POST (it races Claude Code's shutdown), so it
    drops the event as a JSON file in the spool dir. The server drains it here on
    startup and on a timer, making capture independent of the shutdown race.
    """
    import json

    cfg = MemoryConfig()
    spool = Path(cfg.spool_dir)
    if not spool.is_dir():
        return 0
    from .hooks.router import handle_hook_event

    db = _db_path()
    handled = 0
    for f in sorted(spool.glob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt or half-written drop — discard so it can't wedge the queue.
            f.unlink(missing_ok=True)
            continue
        try:
            if isinstance(payload, dict) and payload.get("session_id"):
                handle_hook_event(db, payload)
                handled += 1
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            f.unlink(missing_ok=True)
    return handled


def _start_spool_drainer() -> None:
    import threading
    import time

    cfg = MemoryConfig()
    try:
        Path(cfg.spool_dir).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    def _loop() -> None:
        while True:
            try:
                _drain_spool_once()
            except Exception:
                pass
            time.sleep(_SPOOL_POLL_SECONDS)

    threading.Thread(target=_loop, daemon=True).start()


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

        # Advertise the spool dir for hooks and start draining queued lifecycle
        # events (e.g. SessionEnd drops the previous session raced past shutdown).
        _write_runtime_file()
        _start_spool_drainer()

        import uvicorn

        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
