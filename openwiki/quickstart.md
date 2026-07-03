# myMem0ry — Quickstart

**myMem0ry** is a personal, offline memory system for AI coding agents. It persists facts, decisions, and session context across agents and machines without requiring API keys or cloud services.

- **Scoped memory** — memories attach to `session`, `context` (git branch), `project` (git remote), or `global` scope.
- **Cross-agent handoffs** — transfer active work between agents (e.g., Claude Code → Codex).
- **Semantic search** — full-text (FTS5 / BM25), vector similarity (sqlite-vec), and hybrid RRF fusion.
- **Zero external dependencies** — everything runs on SQLite, spaCy, and optionally ONNX Runtime.

## Repository layout

```
src/mem0ry/
  cli/            Typer CLI commands
  db/             SQLite schema, stores, migration, retention, git-sync
  conversations/  Search backends (BM25, vector, hybrid), text encoders
  web/            Read-only Starlette UI mounted on the MCP server
  hooks/          Lifecycle hook router and agent hook scripts
  dataset/        ChatML dataset builder from OpenAI exports
  pipeline/       High-level dataset pipeline wiring
  mcp_server.py   FastMCP server exposing memory tools
  daemon.py       Auto-daemon management for the HTTP server
  config.py       MemoryConfig — environment-driven settings
  auth.py         Bearer token + Host allowlist middleware

docs/             User-facing guides (install, usage, sync, MCP flow analysis)
hooks/            Shell hook scripts for claude-code, opencode, codex, cursor, gemini-cli
tests/            35+ pytest files covering CLI, DB, MCP, web, search, retention
```

## Setup in one minute

1. **Install** (requires Python 3.11–3.13, `uv`, and `ripgrep` on PATH):
   ```bash
   uv sync --group dev
   mymem0ry doctor          # auto-downloads spaCy model if missing
   ```

2. **Add the MCP server** to your agent:
   ```bash
   # Claude Code
   claude mcp add --scope user mymem0ry -- mymem0ry-mcp
   ```

3. **Install hooks** (optional but recommended for auto-capture):
   ```bash
   mymem0ry hooks --config   # prints snippet to paste into agent settings
   mymem0ry hooks --install  # copies hook scripts to ~/.local/share/mymem0ry/hooks/
   ```

The MCP server auto-starts an HTTP daemon on first run; the web UI is available at `http://127.0.0.1:49374`.

## Key environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MEM0RY_DB_PATH` | `data/memories.db` | Main SQLite database |
| `CONVERSATIONS_DIR` | `data/conversations` | Archived conversation `.md` files |
| `MEMORIES_DIR` | `data/memories` | Curated memories exported as `.md` |
| `SEARCH_BACKEND` | `db` | Search backend for conversations (`db`, `ripgrep`, `fts`, `bm25`, `vector`, `hybrid`) |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model for query expansion and vectors |
| `VECTOR_ENCODER_MODEL` | `spacy` | Vector encoder (`spacy` or `nomic`) |
| `MEM0RY_GIT_AUTO_SYNC` | `0` | Enable git auto-sync on the data directory |
| `MEM0RY_TOKEN` | — | Bearer token for HTTP auth |
| `MEM0RY_HOST` / `MEM0RY_PORT` | `127.0.0.1` / `49374` | HTTP server bind address |

## Where to go next

- **[Architecture overview](architecture/overview.md)** — how CLI, MCP, DB, search, and web UI fit together.
- **[Data model](architecture/data-model.md)** — schema v9, tables, FTS5, sqlite-vec, retention tiers.
- **[Agent setup & workflows](workflows/agent-setup.md)** — MCP transport modes, hooks, scoped memory, handoffs, git sync.
- **[Operations guide](workflows/operations.md)** — CLI commands: context, save, migrate, retention, backup, diagnostics.
- **[MCP & web integration](integrations/mcp-and-web.md)** — MCP tool reference, HTTP routes, auth/CORS.
- **[Testing](testing.md)** — how to run tests, CI pipeline, test organization.

## Important files to know

| File | What it does |
|---|---|
| `src/mem0ry/config.py` | `MemoryConfig` — central source of env vars and defaults |
| `src/mem0ry/mcp_server.py` | FastMCP server with `save_memory`, `get_context`, `search_memory`, etc. |
| `src/mem0ry/db/schema.py` | Schema v9 definition, indexes, FTS5 triggers |
| `src/mem0ry/db/store_memories/__init__.py` | Re-exports all memory CRUD, search, lifecycle, and I/O |
| `src/mem0ry/cli/main.py` | CLI entrypoint — imports all subcommand modules |
| `src/mem0ry/hooks/router.py` | Hook event router — decides which tool calls become observations |
| `src/mem0ry/daemon.py` | Auto-daemon for the HTTP server |
| `src/mem0ry/conversations/search_hybrid.py` | Hybrid BM25 + vector RRF fusion |
| `src/mem0ry/conversations/encoders/factory.py` | Pluggable encoder backend selection |
