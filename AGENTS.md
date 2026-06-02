# AGENTS.md — myMem0ry

Personal memory system with semantic search, scoped storage (session/context/project/global), cross-agent handoffs, and MCP server. Python 3.11+, managed with `uv`.

## Setup

```bash
bin/setup                          # Idempotent bootstrap (deps + spaCy model + ripgrep check)
uv sync --group dev                # Dependencies only
mymem0ry doctor                    # Auto-downloads spaCy model if missing
# For Portuguese: SPACY_MODEL=pt_core_news_lg
```

ripgrep (`rg`) must be on PATH — the default `ripgrep` search backend shells out to it.

## Commands

```bash
# Lint → typecheck → test (CI order, from .github/workflows/ci.yml)
uv run ruff check .
uv run mypy src/mem0ry
uv run pytest                          # coverage gate: fail_under=80 in pyproject.toml

# Single test file or test
uv run pytest tests/test_config.py
uv run pytest tests/test_config.py::test_default_values -k test_default

# CLI entrypoints (from pyproject.toml [project.scripts])
mymem0ry split [source]               # Export → .md by date (auto-detects openai/gemini/claude)
mymem0ry search "query"               # ripgrep default
mymem0ry search "query" --backend hybrid --expand  # BM25+vector RRF fusion + spaCy expansion
mymem0ry index                        # Build BM25 + FTS5 + vector indexes
mymem0ry migrate                      # .md → SQLite structured memories
mymem0ry migrate --reprocess          # Drop DB + reingest into v4 schema
mymem0ry stats                        # DB overview (by scope, type, source, project)
mymem0ry projects                     # List projects with memories (by git remote URL)
mymem0ry doctor                       # System health check (6 checks)
mymem0ry decay [--days 90] [--dry-run]  # Remove old session logs
mymem0ry benchmark "query"            # Compare search backends
mymem0ry expand "token"               # Semantically related tokens
mymem0ry dataset                      # ChatML JSONL (legacy)

# Share (export/import)
mymem0ry export --output file.json    # Export memories+handoffs to JSON
mymem0ry export --project-id X -o out.json  # Export specific project
mymem0ry import file.json             # Import from JSON (skips duplicates)
mymem0ry import file.json --project-id Y    # Import remapping to project Y

# Server & handoffs
mymem0ry serve                         # Start HTTP server (MCP + hooks + handoffs)
mymem0ry serve --detach                # Start in background (daemon mode)
mymem0ry handoff begin --summary "..." # Create handoff for next agent
mymem0ry handoff accept                # Accept pending handoff
mymem0ry handoff status                # Check server status
mymem0ry hooks --config              # Print settings.json snippet for current agent
mymem0ry hooks --path                # Print hooks directory path
mymem0ry observe session-start         # Send lifecycle observation (CLI fallback)

# CLI commands used by hooks (legacy, pre-HTTP)
mymem0ry context --cwd .              # Load context for current project (session-start)
mymem0ry save "Title" "Content"       # Save a memory (session-end)
mymem0ry log "message"                # Quick session log (lifecycle hooks)

# MCP server
mymem0ry-mcp                          # Starts FastMCP server (stdio or HTTP)
```

## Architecture

```
src/mem0ry/
├── config.py                 # MemoryConfig dataclass — loads .env via dotenv
├── auth.py                   # AuthMiddleware + CORSMiddleware — bearer token, host allowlist, CORS
├── web/                      # Read-only Web UI — dark mode, dashboard, projects, search, audit
├── mcp_server.py             # FastMCP server — 11 tools, /hook endpoint, /handoff endpoints, web UI routes
├── daemon.py                 # Auto-daemon: ensure_server(), is_server_running(), stop_server()
├── cli/main.py               # Typer app — all CLI commands (incl. backup, restore)
├── db/
│   ├── connection.py         # SQLite + sqlite-vec extension
│   ├── schema.py             # init_schema() — v7: memories + observations + handoffs + audit_log
│   ├── store.py              # Re-exports from store_memories, store_observations, store_handoffs, store_audit
│   ├── store_memories.py     # CRUD: memories + batch delete, export, import
│   ├── store_handoffs.py     # CRUD: handoffs + export, import
│   ├── retention.py          # Salience scoring, pin/unpin, forget-sweep
│   └── migrate.py            # migrate_v1_to_v2() through migrate_v6_to_v7()
├── hooks/
│   ├── sanitize.py           # sanitize_payload() — strip PII, API keys, truncate
│   └── router.py             # handle_hook_event() — sanitize → resolve context → store
├── parsers/                  # Auto-detected by content shape
│   ├── openai.py             # ChatGPT JSON (mapping tree)
│   ├── gemini.py             # Google Takeout JSON (safeHtmlItem)
│   └── claude.py             # ClaudeCodeParser (JSONL) + ClaudeExportParser (JSON)
├── conversations/
│   ├── writer.py             # split_conversations() → .md files
│   ├── search.py             # ripgrep backend
│   ├── search_bm25.py        # BM25Okapi
│   ├── search_fts.py         # SQLite FTS5
│   ├── search_hybrid.py      # RRF fusion: 1/(k + rank) combining BM25 + vector
│   ├── embeddings.py         # SpacyEncoder — nlp(text).vector, 300-dim
│   ├── vector_store.py       # sqlite-vec wrapper
│   └── spacy_expand.py       # SpacyConceptSearch — query expansion
├── dataset/                  # Legacy ChatML fine-tuning pipeline
└── utils/
    ├── filenames.py          # sanitize_title() — shared by writer.py + mcp_server.py
    ├── git_context.py        # resolve_project_id(), resolve_context(), resolve_full_context()
    ├── logging.py            # configure_logging()
    └── paths.py              # ensure_dir()
```

### Key facts

- **Schema version**: v7. `db/schema.py` sets `_SCHEMA_VERSION = 7`. Tables: `memories`, `observations`, `handoffs`, `audit_log`, `schema_meta`. Column `superseded_by` on memories tracks fact evolution chain.
- **Memory scopes**: `global` / `project` / `context` / `session` — validated by `_VALID_SCOPES` in `db/store.py`.
- **Memory types**: `fact` / `decision` / `pattern` / `log` — validated by `_VALID_MEMORY_TYPES` in `db/store.py`. Used for decay differentiation.
- **Source values**: `claude-code` / `opencode` / `codex` / `manual` / `import` / `hook` — validated by `_VALID_SOURCES` in `db/store.py`.
- **Observation kinds**: `session-start` / `user-prompt` / `post-tool-use` / `pre-compact` / `session-end` / `log` / `other` — validated by `_VALID_KINDS` in `db/store.py` and `hooks/sanitize.py`.
- **Handoff lifecycle**: `open` → `accepted` or `expired` (auto-expires after 7 days). Matched by `project_id`.
- **`get_context()`** aggregates session → context → project → global (4-level cascata), returning up to `top_k` results distributed across scopes.
- **Project resolution**: `resolve_project_id()` uses `git remote get-url origin` (raw URL). Falls back to None if not a git repo. See `utils/git_context.py`.
- **Context resolution**: `resolve_context()` uses `git rev-parse --abbrev-ref HEAD`. Generic — can be branch, worktree, feature, etc.
- **Hook architecture**: Hooks `curl POST /hook` to the HTTP server (fire-and-forget). Sanitization in `hooks/sanitize.py`. Router handles all writes: logging (`kind=log`), conversation archiving (`session-end` with `messages` **or** a `transcript_path` the server parses), auto-handoff on session end.
- **Hook `session_id`**: Claude Code hook scripts read the real `session_id` (and `cwd`, `transcript_path`) from the stdin JSON payload — they must NOT fabricate one. Auto-handoff (`auto_handoff_from_session`) gathers a session's observations by `session_id`; a per-invocation timestamp id would group nothing and produce no handoff.
- **Hook-based writes (zero LLM tokens)**: Conversation archiving, message logging, session end → all handled by `/hook` endpoint. The LLM never serializes conversations.
- **Auto-daemon**: `daemon.py` manages PID file + health check. `ensure_server()` starts server if not running.
- **MCP server** uses module-level global state (`_session_id`, `_expander`) with lazy init — not thread-safe.
- **MCP tools** (11, reads + selective writes): get_context, save_memory, search_memory, read_memory, memory_stats, memory_handoff_begin, memory_handoff_accept, memory_pin, memory_unpin, memory_forget_sweep, evolve_fact. Each must carry `@mcp.tool()` — a dropped decorator silently unregisters the tool (this bit `memory_handoff_begin`). `test_mcp_server.py` guards registration.
- **Token philosophy**: Tools are for reads + selective writes (save_memory for facts/decisions). Bulk writes (conversation archiving, logging) are hook-only to avoid burning LLM tokens.
- **HTTP endpoints**: `GET /health`, `POST /hook`, `GET /handoff/accept`.
- **Web UI**: `web/` — dark mode viewer mounted on MCP server. Routes: `/` (dashboard), `/projects`, `/project/{id}`, `/memory/{id}`, `/search`, `/audit`, `/api/memories`, `/import`, `/memories/batch-delete`, `/memories/export`, `/memories/import`. Checkboxes + batch action bar for delete/export. Per-project "Export Project" button.
- **Auth**: `auth.py` — Bearer token (`MEM0RY_TOKEN`), Host allowlisting (`MEM0RY_ALLOWED_HOSTS`), CORS (`MEM0RY_CORS_ORIGINS`). Applied as Starlette middleware on HTTP transport.
- **Audit log**: `audit_log` table records mutations (create, delete, import, handoff, evolve). Auto-recorded in `store.py`.
- **Retention**: `db/retention.py` — salience-based decay. Tiers: working(log,90d), procedural(pattern,365d), semantic(fact/decision,indefinite+auto-pin).
- **Fact evolution**: `evolve_fact` MCP tool lets the agent LLM consolidate contradictory facts. Old facts get `superseded_by` set + soft-delete; a new evolved fact is created. `get_context()` and `search_memories()` exclude superseded memories. The agent decides when to evolve (Camada 1 — instruction-based, no heuristics).
- `sanitize_title()` in `utils/filenames.py` is the single source for filename sanitization, shared between `writer.py` and `mcp_server.py`.
- `config.py` loads `.env` from the project root on import (`load_dotenv` at module level).
- `data/` is gitignored. DB files (`data/memories.db`, `data/conversations/.vec.db`) are created at runtime.

## Tests

- No `conftest.py`. Tests import directly from `mem0ry.*`.
- Tests use `pytest.fixture` for temp DBs in `test_db_store.py`, `test_handoffs.py`, `test_observations.py`.
- Coverage enforced at 80% (`fail_under = 80` in `pyproject.toml`).
- `mutmut` is configured for mutation testing (`uv run mutmut run`).

## Code style

- Functions: 4–20 lines. Files: under 500 lines.
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
- Types: explicit. No `Any`, no untyped functions.
- Max 2 levels of indentation. Early returns over nesting.
- Exception messages include the offending value and expected shape.
- Preserve existing comments on refactor — they carry intent.
- Docstrings: WHY + one usage example on public functions.
- Format/lint with `ruff` only. No style discussion beyond that.
- Structured JSON for debug logging, plain text for CLI output.
