# Architecture Overview

myMem0ry is a locally-running Python package built around a **FastMCP server**, a **SQLite database**, and a **read-only Starlette web UI**. All components share the same `MemoryConfig` and data directory.

## High-level flow

```
┌─────────────┐    stdio/HTTP     ┌─────────────────┐
│  AI Agent   │ ────────────────► │  MCP Server     │
│  (Claude,   │                   │  (FastMCP)      │
│   Codex…)   │ ◄───────────────  │                 │
└─────────────┘                   └────────┬────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
              ┌─────────┐         ┌────────────┐        ┌──────────┐
              │  Hooks  │         │  SQLite DB │        │ Web UI   │
              │ Router  │         │  + sqlite-vec│        │(Starlette│
              └────┬────┘         └────────────┘        └──────────┘
                   │
                   ▼
            ┌─────────────┐
            │ Observations│
            │   (audit)   │
            └─────────────┘
```

## Layers

### 1. CLI (`src/mem0ry/cli/`)

A [Typer](https://typer.tiangolo.com/) application rooted in `cli/_app.py` and assembled in `cli/main.py`. Each subcommand lives in its own module:

- `backup.py` — `mymem0ry backup` / `restore`
- `conversation.py` — `mymem0ry split`, `index`, `search`
- `diagnostics.py` — `mymem0ry doctor`, `version`, `stats`, `projects`
- `git_sync.py` — `mymem0ry git-sync status` / `pull` / `push`
- `handoff.py` — `mymem0ry handoff`, `handoff accept`, `handoff status`
- `hooks.py` — `mymem0ry hooks --config` / `--install` / `--path`
- `memory.py` — `mymem0ry context`, `save`, `migrate`, `dataset`, `decay`, `pin` / `unpin`, `forget-sweep`
- `migration.py` — `mymem0ry migrate`
- `retention.py` — `mymem0ry decay`, `forget-sweep`
- `server.py` — `mymem0ry serve [--detach]`
- `share.py` — `mymem0ry share`, `receive`

The CLI is also the surface for **hooks**: `mymem0ry context`, `mymem0ry save`, and `mymem0ry log` are called by shell scripts in `hooks/<agent>/`.

### 2. MCP Server (`src/mem0ry/mcp_server.py`)

Built on `mcp.server.fastmcp.FastMCP`. It exposes tools that agents call directly:

| Tool | Purpose |
|---|---|
| `save_memory` | Persist a curated memory (fact, decision, log) |
| `get_context` | Aggregate memories across scopes for the current session |
| `search_memory` | Search curated memories with optional query expansion |
| `search_conversations` | Broad search across archived conversation `.md` files |
| `read_memory` | Retrieve a single memory or conversation transcript by path |
| `memory_pin` / `memory_unpin` | Exempt a memory from retention decay |
| `begin_handoff` / `accept_handoff` / `close_handoff` | Cross-agent handoffs |

The server auto-starts the HTTP daemon (see `daemon.py`) when running with `streamable-http` transport, so the web UI is available without a separate `serve` command.

### 3. Database layer (`src/mem0ry/db/`)

- **`connection.py`** — opens SQLite with `sqlite-vec` loaded, WAL journal mode, and `sqlite3.Row` factory.
- **`schema.py`** — schema v9: `memories`, `observations`, `handoffs`, `audit_log`, `schema_meta`, plus FTS5 triggers and indexes.
- **`store_memories/`** — 8 focused modules replacing the former monolithic `store_memories.py`:
  - `crud.py` — create, read, update, delete
  - `search.py` — filtered FTS5 / vector / hybrid search
  - `context.py` — `get_context` with scope priority (session → context → project → global)
  - `lifecycle.py` — `end_session`, `pin`/`unpin`, `touch`, `track_reads`, `decay`
  - `io.py` — `export_memories`, `import_memories`, `evolve_memories`
  - `stats.py` — `stats`, `list_projects`, `list_scopes`
  - `helpers.py` — constants and query helpers
- **`store_observations.py`** — write and read agent observations.
- **`store_handoffs.py`** — handoff CRUD and expiration.
- **`store_audit.py`** — audit log writes.
- **`retention.py`** — salience scoring, tier mapping, forget sweep, soft/hard delete.
- **`migrate.py`** — schema migrations from older versions.
- **`git_sync.py`** — git-based auto-sync for the data directory.

### 4. Search pipeline (`src/mem0ry/conversations/`)

Search is pluggable via `SEARCH_BACKEND` env var:

| Backend | Implementation | Notes |
|---|---|---|
| `ripgrep` | `search_ripgrep.py` | Fast filename search, shells out to `rg` |
| `fts` | `search_fts.py` | SQLite FTS5 on conversation files |
| `bm25` | `search_bm25.py` | Okapi BM25 ranking |
| `vector` | `vector_store.py` + encoder | Cosine similarity via `sqlite-vec` |
| `hybrid` | `search_hybrid.py` | RRF fusion of BM25 + vector results |

**Encoders** (`src/mem0ry/conversations/encoders/`):
- `SpacyEncoder` — default, uses spaCy doc vectors.
- `NomicOnnxEncoder` — ONNX Runtime wrapper for `nomic-ai/nomic-embed-text-v1.5`; set `VECTOR_ENCODER_MODEL=nomic`.

### 5. Web UI (`src/mem0ry/web/`)

A read-only Starlette app mounted on the MCP HTTP server. Routes are defined in `web/__init__.py` and handlers live in `web/pages/`:

- `/` — dashboard with stats
- `/projects` — project list
- `/project/{id}` — project detail + memories
- `/project/{id}/observations` — project observations
- `/memory/{id}` — memory detail / edit
- `/search` — search page
- `/handoffs` — handoff list
- `/export`, `/import` — JSON export / import
- `/trash` — deleted memories
- `/audit` — audit log

Templates are plain Python functions in `web/templates.py` returning HTML strings (no external template engine).

### 6. Hooks (`src/mem0ry/hooks/`)

- **`router.py`** — receives hook events, sanitizes payloads, resolves context, and persists observations. Only **mutating tools** (`Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `str_replace_editor`, `create_file`, `apply_patch`) create observations; reads are ignored to avoid noise.
- **`hooks/<agent>/`** — shell scripts for `session-start`, `session-end`, and per-message logging. `mymem0ry hooks --config` prints the JSON snippet needed for each agent.

### 7. Dataset pipeline (`src/mem0ry/dataset/` and `pipeline/`)

Optional flow for building ChatML training datasets from exported conversations:

1. Parse OpenAI export JSON → `ParsedConversation`
2. Build ChatML examples with overlap and length limits (`builder.py`)
3. Apply quality filters (`filter.py`), deduplicate (`dedupe.py`), temporal enrichment (`temporal.py`)
4. Train/validation split (`splitter.py`)
5. Write JSONL (`pipeline/dataset.py`)

## Entrypoints

| Entrypoint | File | Used by |
|---|---|---|
| `mymem0ry` | `pyproject.toml` scripts → `mem0ry.cli.main:app` | Human CLI |
| `mymem0ry-mcp` | `pyproject.toml` scripts → `mem0ry.mcp_server:mcp` | Agents (stdio) |
| `mem0ry.mcp_server:run_http_server` | `mcp_server.py` | Agents (HTTP) / Docker |

## Configuration

Everything flows through `MemoryConfig` in `src/mem0ry/config.py`. It reads env vars with sensible defaults and derives paths from the project root or `XDG_DATA_HOME`.
