# AGENTS.md — myMem0ry

Personal memory system for AI coding agents. Python 3.11+, managed with `uv`. Offline, zero API keys, cross-agent handoffs, MCP server, semantic search via spaCy + sqlite-vec.

## Setup

```bash
bin/setup                          # Idempotent bootstrap (deps + spaCy model + ripgrep check)
uv sync --group dev                # Dependencies only
uv run mymem0ry doctor             # Health check; auto-downloads spaCy model if missing
```

- **ripgrep (`rg`) on PATH is required** — the default `ripgrep` search backend shells out to it.
- Default `SPACY_MODEL` in `config.py:56` is `en_core_news_lg`. The repo's `.env` overrides to `pt_core_news_lg` (Portuguese). Set `SPACY_MODEL` in `.env` before `mymem0ry doctor` for the first run.
- `data/` is gitignored. DB files (`data/memories.db`, `data/conversations/.vec.db`) and the spool dir are created at runtime.

## CI order (from `.github/workflows/ci.yml`)

```bash
uv run ruff check .                # lint (no ruff format in CI — local only)
uv run mypy src/mem0ry             # typecheck (mypy.ini missing imports for spacy/sqlite-vec/rank_bm25)
uv run python -m pytest --cov      # tests + coverage (fail_under=80, pyproject.toml:81)
```

## Single-test shortcuts

```bash
uv run pytest tests/test_db_store.py                          # one file
uv run pytest tests/test_db_store.py::TestClass::test_thing    # one test
uv run pytest -k "test_default"                                # name match
uv run pytest -x                                                # stop on first failure
```

## CLI entrypoints (from `pyproject.toml [project.scripts]`)

```bash
mymem0ry search "query"                    # ripgrep default
mymem0ry search "query" --backend hybrid --expand   # BM25+vector RRF + spaCy expansion
mymem0ry index                             # Build BM25 + FTS5 + vector indexes
mymem0ry split [source]                    # Export → .md by date (auto-detects openai/gemini/claude)
mymem0ry migrate                           # .md → SQLite structured memories
mymem0ry migrate --reprocess               # Drop DB + reingest
mymem0ry stats                             # DB overview (by scope, type, source, project)
mymem0ry projects                          # List projects with memories (by git remote URL)
mymem0ry doctor                            # 6-check system health
mymem0ry decay [--days 90] [--dry-run]     # Remove old session logs
mymem0ry benchmark "query"                 # Compare search backends
mymem0ry expand "token"                    # Semantically related tokens
mymem0ry backup --to file.tar.gz           # DB + conversations
mymem0ry restore --from file.tar.gz

# Share
mymem0ry export --output file.json
mymem0ry export --project-id X -o out.json
mymem0ry import file.json
mymem0ry import file.json --project-id Y   # remap to project Y on import

# Server & handoffs
mymem0ry serve                             # Foreground HTTP (MCP + hooks + handoffs + web UI)
mymem0ry serve --detach                    # Background (daemon.py manages PID + health)
mymem0ry handoff begin --summary "..."     # Create handoff for next agent
mymem0ry handoff accept                    # Peek pending handoff for current project
mymem0ry handoff status                    # Check server status
mymem0ry hooks --config                    # Print settings.json snippet for current agent
mymem0ry hooks --path                      # Print hooks dir path
mymem0ry hooks --install                   # Install hooks for detected agent
mymem0ry observe session-start             # Send lifecycle observation (CLI fallback)

# Legacy (pre-HTTP) — still used by some hook scripts
mymem0ry context --cwd .
mymem0ry save "Title" "Content"
mymem0ry log "message"

# MCP server (separate entrypoint)
mymem0ry-mcp                               # FastMCP server (stdio or streamable-http)
```

## Repo layout

```
src/mem0ry/
├── config.py                # MemoryConfig — loads .env via dotenv at import time
├── auth.py                  # Bearer token + host allowlist + CORS middleware
├── daemon.py                # ensure_server(), is_server_running(), stop_server()
├── mcp_server.py            # FastMCP server: 12 @mcp.tool() + HTTP routes + web UI mount
├── cli/main.py              # Typer app — all CLI commands (incl. backup, restore)
├── db/
│   ├── connection.py        # SQLite + sqlite-vec extension
│   ├── schema.py            # _SCHEMA_VERSION = 8 (memories, observations, handoffs, audit_log, schema_meta)
│   ├── migrate.py           # migrate_v1_to_v2 … migrate_v7_to_v8
│   ├── store.py             # Re-exports from store_memories, store_observations, store_handoffs, store_audit
│   ├── store_memories.py    # CRUD + batch delete, export, import
│   ├── store_handoffs.py    # CRUD + export, import
│   ├── store_audit.py       # Audit log writes
│   ├── store_observations.py
│   └── retention.py         # Salience scoring, pin/unpin, forget-sweep
├── hooks/
│   ├── sanitize.py          # sanitize_payload() — strip PII, API keys, truncate
│   └── router.py            # handle_hook_event() — sanitize → resolve context → store
├── parsers/                 # Auto-detected by content shape
│   ├── base.py              # BaseParser + ParsedConversation
│   ├── openai.py            # ChatGPT JSON (mapping tree)
│   ├── gemini.py            # Google Takeout JSON (safeHtmlItem)
│   └── claude.py            # ClaudeCodeParser (JSONL) + ClaudeExportParser (JSON)
├── conversations/
│   ├── writer.py            # split_conversations() → .md files
│   ├── search.py            # ripgrep backend
│   ├── search_bm25.py       # BM25Okapi
│   ├── search_fts.py        # SQLite FTS5
│   ├── search_hybrid.py     # RRF fusion: 1/(k + rank) over BM25 + vector
│   ├── embeddings.py        # SpacyEncoder — nlp(text).vector, 300-dim
│   ├── vector_store.py      # sqlite-vec wrapper
│   └── spacy_expand.py      # SpacyConceptSearch — query expansion
├── dataset/                 # Legacy ChatML fine-tuning pipeline
├── web/                     # Starlette app: pages.py (routes), templates.py (Jinja), i18n.py
├── utils/                   # filenames, git_context, logging, paths, update_check
├── pipeline/                # (stub)
└── training/                # (stub)

hooks/                       # Bash hook scripts shipped at repo root (NOT in src/)
├── claude-code/             # session-start.sh, session-end.sh, mymem0ry-hook.sh
├── codex/
├── cursor/
├── gemini-cli/
└── opencode/                # mymem0ry-hook.sh only (OpenCode has no native lifecycle hooks)

tests/                       # No fixtures in conftest beyond env vars; see below
docker/                      # Dockerfile + docker-compose.yml
docs/                        # install.md, usage.md, analise-fluxo-mcp.md
```

## Schema and validation (v8)

- **Schema version**: 8. `db/schema.py:7` sets `_SCHEMA_VERSION = 8`. Tables: `memories`, `observations`, `handoffs`, `audit_log`, `schema_meta`. `memories.superseded_by` tracks fact evolution.
- **Migrations live in `db/migrate.py`**: chained `migrate_v{N}_to_v{N+1}` functions. Schema init runs all migrations in order on a fresh DB.
- **Enums** are validated centrally in `db/store.py` and re-imported by callers — adding a value requires editing that file:
  - **Scopes** (`_VALID_SCOPES`): `global` / `project` / `context` / `session`
  - **Memory types** (`_VALID_MEMORY_TYPES`): `fact` / `decision` / `pattern` / `log` (used for decay differentiation)
  - **Sources** (`_VALID_SOURCES`): `claude-code` / `opencode` / `codex` / `manual` / `import` / `hook`
  - **Observation kinds** (`_VALID_KINDS`): `session-start` / `user-prompt` / `post-tool-use` / `pre-compact` / `session-end` / `log` / `other`

## Scoping and resolution

- **`get_context()`** aggregates `session → context → project → global` (4-level cascade), returning up to `top_k` distributed across scopes.
- **Project** = `git remote get-url origin` raw URL (`utils/git_context.py:resolve_project_id`). Falls back to `None` outside a git repo.
- **Context** = `git rev-parse --abbrev-ref HEAD` (`utils/git_context.py:resolve_context`). Generic — branch, worktree, feature.

## Hook architecture

- Hooks `curl POST /hook` on the HTTP server (fire-and-forget, `--max-time 0.2` in OpenCode script). Server auto-starts when MCP server runs — no separate `serve` step needed.
- **Spool dir for unreliable events** (`mcp_server.py:_drain_spool_once`, `_start_spool_drainer`): SessionEnd hook races Claude Code's shutdown, so the hook drops the event as a JSON file in `MEM0RY_SPOOL_DIR` (default `<data_dir>/spool`). The server drains it on startup and on a background timer. Do not assume the POST always succeeds.
- **Spool dir + server URL are advertised via a runtime file** (`mcp_server.py:write_runtime_file`) so bash hooks can read the path without env coordination. Plain text: line 1 = spool dir, line 2 = url.
- **Hook `session_id` must be the real one** — Claude Code hook scripts read `session_id` (and `cwd`, `transcript_path`) from the stdin JSON payload. Do NOT fabricate a per-invocation id: `auto_handoff_from_session` groups observations by `session_id` and a fresh id each time groups nothing.
- **Hook writes (zero LLM tokens)**: conversation archiving (`session-end` with `messages` **or** `transcript_path` parsed by server), logging (`kind=log`), lifecycle observations. The LLM never serializes conversations.
- **OpenCode has no native hook framework** — the `hooks/opencode/mymem0ry-hook.sh` script is invoked manually (e.g. by a wrapper) and the MCP tools (`get_context`, `save_memory`) carry the load.

## MCP server quirks

- **12 tools, each with `@mcp.tool()`** — a dropped decorator silently unregisters the tool (this bit `memory_handoff_begin` once). `tests/test_mcp_server.py` guards registration. List: `save_memory`, `get_context`, `search_memory`, `search_conversations`, `read_memory`, `memory_handoff_begin`, `memory_handoff_accept`, `memory_pin`, `memory_unpin`, `memory_forget_sweep`, `evolve_fact`, `memory_stats`.
- **Module-level globals** (`_session_id`, `_expander`) with lazy init — not thread-safe. The server assumes one MCP client process.
- **Token philosophy**: MCP tools are reads + selective writes (`save_memory` for facts/decisions). Bulk writes (conversation archiving, logging) are hook-only to avoid burning LLM tokens.
- **HTTP endpoints on streamable-http transport**: `GET /health`, `POST /hook`, `GET /handoff/accept`. Web UI mounted from `web/__init__.py` (25 routes — see web block below).

## Web UI

Routes live in `web/__init__.py` (Starlette `Route(...)` list). All read-only except for explicit `methods=["POST"]` routes. Full set:

- Pages: `/`, `/projects`, `/project/{id}`, `/project/{id}/observations`, `/memory/{id}`, `/memory/{id}/edit` (GET+POST), `/memory/{id}/{pin,unpin,restore,delete}` (POST), `/observation/{id}`, `/observation/{id}/delete` (POST), `/trash`, `/handoffs`, `/handoff/{id}`, `/handoff/{id}/{close,delete}` (POST), `/search`, `/audit`, `/import` (GET), `/memories/import` (POST).
- APIs: `/api/memories`, `/memories/batch-delete` (POST), `/memories/export` (POST).
- Dark mode, no JS framework — Jinja templates in `web/templates.py`, i18n in `web/i18n.py`.

## Auth

- `auth.py` — Bearer token (`MEM0RY_TOKEN`), host allowlist (`MEM0RY_ALLOWED_HOSTS`, default `localhost,127.0.0.1`, DNS-rebinding protection), CORS (`MEM0RY_CORS_ORIGINS`). Applied as Starlette middleware on the HTTP transport.
- Empty `MEM0RY_TOKEN` skips auth (dev only).

## Retention and fact evolution

- `db/retention.py` — salience-based decay. Tiers: `log` (working, 90d), `pattern` (procedural, 365d), `fact`/`decision` (semantic, indefinite, auto-pinned).
- `evolve_fact` MCP tool (`mcp_server.py:530`) — agent LLM consolidates contradictory facts. Old facts get `superseded_by` set + soft-deleted; a new evolved fact is created. `get_context()` and `search_memories()` exclude superseded rows. The agent decides when to evolve (no heuristics, instruction-based).
- `audit_log` records mutations (create, delete, import, handoff, evolve) — auto-written in `store.py`.

## Env (loaded at `config.py` import time via `load_dotenv`)

| Var | Default | Purpose |
|---|---|---|
| `DB_PATH` | `data/memories.db` | SQLite memories DB (source of truth) |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |
| `CONVERSATIONS_DIR` | `data/conversations` | Archived conversation `.md` files |
| `MEMORIES_DIR` | `data/memories` | Curated memory `.md` exports (kept separate from conversations) |
| `MEM0RY_SPOOL_DIR` | `<db_dir>/spool` | Drop-box for lifecycle events the hook can't POST |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model for embeddings + search |
| `MEM0RY_HOST` | `127.0.0.1` | HTTP host |
| `MEM0RY_PORT` | `49374` | HTTP port |
| `MEM0RY_TOKEN` | _(empty)_ | Bearer token (empty = no auth) |
| `MEM0RY_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Host allowlist |
| `MEM0RY_CORS_ORIGINS` | _(empty)_ | CORS origins for web UI |
| `MEM0RY_PID_FILE` | `data/server.pid` | Daemon PID file |
| `MEM0RY_NO_UPDATE_CHECK` | _(unset)_ | Set `1` to skip CLI update check (CI does this via `tests/conftest.py:3`) |
| `EMBEDDING_DIM` | `300` | Vector dimensionality (must match spaCy model) |
| `RRF_K` | `60` | RRF fusion constant |
| `EXPAND_TOP_K` | `10` | spaCy concept expansion depth |
| `SEARCH_TOP_K` | `3` | Default search result count |
| `SEARCH_BACKEND` | `ripgrep` | Default backend |
| `MCP_TRANSPORT` | _(unset)_ | Set to `streamable-http` to expose web UI |

## Tests

- `tests/conftest.py` sets `MEM0RY_NO_UPDATE_CHECK=1` to silence the CLI update check during the test run.
- Tests import directly from `mem0ry.*` — there is no shared `conftest` fixture set. Per-file `pytest.fixture` for temp DBs lives in `test_db_store.py`, `test_handoffs.py`, `test_observations.py`.
- Coverage gate: `fail_under = 80` (`pyproject.toml:81`).
- `mutmut` is configured (`pyproject.toml:83-87`) — `uv run mutmut run`. Mutation scope is `src/mem0ry`; `test_*` and `__init__.py` are excluded.
- Mutation regression suite: `tests/test_sonarqube_regression.py` is large and slow — skip with `-k` if iterating.

## Code style

- Functions: 4–20 lines. Files: under 500 lines. Split by responsibility.
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
- Types: explicit. No `Any`, no `Dict`, no untyped functions.
- Max 2 levels of indentation. Early returns over nesting.
- Exception messages include the offending value and expected shape.
- Preserve existing comments on refactor — they carry intent.
- Docstrings: WHY + one usage example on public functions.
- `ruff` only for lint/format. No style discussion beyond that.
- Structured JSON for debug logging, plain text for CLI output.
- No `print()` in library code — use `logging`. (CONTRIBUTING.md:55)

## Adding things (from `CONTRIBUTING.md`)

- **New parser**: subclass `BaseParser` in `parsers/base.py`, implement `parse(source_dir) -> list[ParsedConversation]`, register in `writer.py` auto-detection, add `tests/test_parser_<source>.py`.
- **New MCP tool**: add to `mcp_server.py` with `@mcp.tool()` decorator, add a registration test in `tests/test_mcp_server.py`.
- **New memory/source/kind value**: edit the matching `_VALID_*` set in `db/store.py`. Add a v{N+1} migration in `db/migrate.py` and bump `_SCHEMA_VERSION` in `db/schema.py`.

## Gotchas

- `config.py` calls `load_dotenv` at **module level** — importing `mem0ry` re-reads `.env`. Test isolation requires `monkeypatch.setenv` before import or `tmp_path` `.env` setup.
- `_default_data_dir()` in `config.py:17` switches to `~/.local/share/mem0ry` (or `%APPDATA%\mem0ry` on Windows) when the package is installed in `site-packages`/`mem0ry`. Development installs use `<project_root>/data/`.
- `mcp_server.py` keeps the `MEM0RY_SESSION_ID` and `SpacyConceptSearch` as module globals — restart the process to reset between unrelated sessions.
- `data/` is created lazily on first DB connection, not on install.
- The `pipeline/` and `training/` directories exist in the tree but are empty stubs — ignore unless extending the fine-tuning pipeline.
