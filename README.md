<div align="center">

# myMem0ry

**Personal memory for AI coding agents. Offline. Zero API keys. Works with any agent.**

[![CI](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml/badge.svg)](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml)
[![Publish](https://github.com/cccadet/myMem0ry/actions/workflows/publish.yml/badge.svg)](https://github.com/cccadet/myMem0ry/actions/workflows/publish.yml)
[![PyPI](https://img.shields.io/pypi/v/mymem0ry?color=blue)](https://pypi.org/project/mymem0ry/)
[![Python](https://img.shields.io/pypi/pyversions/mymem0ry)](https://pypi.org/project/mymem0ry/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

Persistent memory that any AI agent can read and write. Quit Claude Code mid-task, open Codex in the same directory — it picks up where you left off.

## Features

- **Scoped memory** — session → context (branch) → project → global, resolved automatically from `cwd`
- **Cross-agent handoffs** — typed records with summary, open questions, next steps
- **Semantic search** — spaCy + sqlite-vec + BM25/FTS5/hybrid RRF fusion
- **Lifecycle hooks** — fire-and-forget HTTP endpoint, payload sanitization, immutable observations
- **Zero LLM tokens for writes** — bulk writes (conversation archiving, logging) via hooks only
- **Retention** — salience-based decay with tiers (working/procedural/semantic), pin/unpin
- **Auth** — Bearer token, host allowlisting, CORS
- **Web UI** — dark mode read-only viewer (dashboard, projects, search, audit log)
- **Backup/restore** — tarball CLI commands
- **Multi-agent** — Claude Code, OpenCode, Codex, Cursor, Gemini CLI, VS Code, Docker

## Install

```bash
pip install uv        # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install mymem0ry
mymem0ry doctor       # checks + auto-installs spaCy model
```

The default spaCy model is Portuguese (`pt_core_news_lg`). For English, set `SPACY_MODEL=en_core_web_lg` in `.env` before running `mymem0ry doctor`.

**Zero config**: after install, just add the MCP server + hooks to your agent config below.
The HTTP server auto-starts when the MCP server runs — no separate `serve` command needed.

## Agent Setup

### Claude Code

```bash
claude mcp add --scope user mymem0ry -- mymem0ry-mcp
```

MCP + hooks in `~/.claude/settings.json`:

First get the correct hooks paths:

```bash
mymem0ry hooks --config
```

Then copy the printed snippet into your `settings.json`. Example result:

```json
{
  "mcpServers": {
    "mymem0ry": {
      "type": "stdio",
      "command": "mymem0ry-mcp"
    }
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "/home/user/.local/share/mymem0ry/hooks/claude-code/session-start.sh"}]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "/home/user/.local/share/mymem0ry/hooks/claude-code/session-end.sh"}]
      }
    ]
  }
}
```

### OpenCode

Add to `~/.config/opencode/opencode.json` (global) or `./opencode.json` (project):

```json
{
  "mcp": {
    "mymem0ry": {
      "type": "local",
      "command": ["mymem0ry-mcp"],
      "timeout": 30000,
      "enabled": true
    }
  }
}
```

> **Note:** `timeout: 30000` (30s) is recommended because loading the spaCy model on first run can exceed the default 5s timeout.

If `mymem0ry-mcp` is not on PATH (e.g. installed via `uv sync` in a project), use the full path:

```json
{
  "mcp": {
    "mymem0ry": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/path/to/myMem0ry", "mymem0ry-mcp"],
      "timeout": 30000,
      "enabled": true
    }
  }
}
```

### Codex CLI

```bash
codex mcp add mymem0ry -- mymem0ry-mcp
```

### VS Code

```bash
code --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
```

### Cursor

```bash
cursor --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
```

### Gemini CLI

Same stdio pattern. Add to Gemini CLI MCP config with `command: mymem0ry-mcp`.

### Docker

```bash
docker compose -f docker/docker-compose.yml up -d
curl http://127.0.0.1:49374/health
```

For detailed per-agent instructions: [docs/install.md](docs/install.md)

## Lifecycle Hooks

Hooks POST lifecycle events to `POST /hook` on the myMem0ry HTTP server.
The server auto-starts when the MCP server runs — no manual `serve` step needed.

| Agent | Hooks | How |
|---|---|---|
| **OpenCode** | MCP only | No hook support — context via MCP tools (`get_context`, `save_memory`) |
| **Claude Code** | Native | `hooks` in `~/.claude/settings.json` — scripts receive full payload via stdin |
| **Codex CLI** | Hook scripts | `codex hook add session-end ./hook-session-end.sh` |
| **Generic** | Manual | `curl -X POST http://127.0.0.1:49374/hook ...` |

Hook payload fields:

| Field | Required | Description |
|---|---|---|
| `kind` | yes | `session-start`, `session-end`, `log`, `user-prompt`, `post-tool-use`, `pre-compact` |
| `session_id` | yes | Unique session identifier (max 64 chars) |
| `agent` | no | `opencode`, `claude-code`, `codex`, `manual`, `hook` |
| `cwd` | no | Working directory for context resolution |
| `transcript_path` | no | Path to a Claude Code transcript JSONL — on `session-end` the server parses it and archives the conversation (zero LLM tokens) |
| `title` | no | Short label (max 500 chars) |
| `body` | no | Content (max 10,000 chars) |
| `messages` | no | `[{"role": "user"|"assistant", "content": "..."}]` — archived as .md |

All payloads are sanitized: secrets redacted, home paths stripped, fields truncated.

## Configuration

All via environment variables (or `.env` file in the project root):

| Variable | Default | Description |
|---|---|---|
| `CONVERSATIONS_DIR` | `data/conversations` | Where archived conversation `.md` files are stored |
| `MEMORIES_DIR` | `data/memories` | Where curated memory `.md` exports are stored (kept separate so general search doesn't bury them) |
| `DB_PATH` | `data/memories.db` | SQLite memories database (source of truth) |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |
| `SPACY_MODEL` | `pt_core_news_lg` | spaCy model for embeddings and search (set `en_core_web_lg` for English) |
| `MEM0RY_HOST` | `127.0.0.1` | Host for HTTP transport |
| `MEM0RY_PORT` | `49374` | Port for HTTP transport |
| `MEM0RY_TOKEN` | _(empty)_ | Bearer token for HTTP auth (skip = no auth) |
| `MEM0RY_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Host allowlist (DNS rebinding protection) |
| `MEM0RY_CORS_ORIGINS` | _(empty)_ | CORS origins for web UI |

```bash
# Custom storage location
export DB_PATH=/path/to/shared/memories.db
export CONVERSATIONS_DIR=/path/to/shared/conversations

# Portuguese language support
export SPACY_MODEL=pt_core_news_lg
mymem0ry doctor
```

## Import Conversations

myMem0ry auto-detects the format. Supports ChatGPT, Gemini, and Claude exports.

```bash
mymem0ry split                                    # Auto-detect
mymem0ry split --source path/to/chatgpt-export    # Specific source
mymem0ry split --source path/to/data --type claude-code  # Force parser

mymem0ry index                                    # Build indexes
mymem0ry migrate                                  # Migrate to structured memory
```

## CLI Commands

```bash
# Context & search
mymem0ry context --cwd .                          # Load context for current project
mymem0ry save "Title" "Content" --scope project   # Save a memory
mymem0ry log "message"                            # Quick session log
mymem0ry search "query"                           # ripgrep search
mymem0ry search "query" --backend hybrid --expand # BM25+vector RRF fusion

# Overview
mymem0ry stats                                    # Database overview
mymem0ry projects                                 # List projects with memories
mymem0ry doctor                                   # System health check

# Retention
mymem0ry decay --days 90 --dry-run                # Preview decay
mymem0ry pin <memory_id>                          # Pin memory (exempt from decay)
mymem0ry unpin <memory_id>
mymem0ry forget-sweep --dry-run                   # Preview salience-based sweep

# Handoffs
mymem0ry handoff begin --summary "..."            # Create handoff for next agent
mymem0ry handoff accept                           # Accept pending handoff
mymem0ry handoff status                           # Check server status

# Hooks
mymem0ry hooks --config                       # Print settings.json snippet
mymem0ry hooks --path                         # Print hooks directory path
mymem0ry hooks --install                      # Install hooks for detected agent

# Server & backup
mymem0ry serve                                    # Start HTTP server
mymem0ry serve --detach                           # Start in background
mymem0ry backup --to backup.tar.gz                # Backup DB + conversations
mymem0ry restore --from backup.tar.gz             # Restore from backup
```

## Memory Scopes

Resolved automatically from `cwd` — no manual configuration needed:

| Scope | Identifier | What it stores | Example |
|---|---|---|---|
| `session` | auto UUID | Current session state | "Trying to fix auth bug" |
| `context` | git branch | Decisions for a branch | "On feat/auth, using JWT" |
| `project` | git remote URL | Project architecture | "Uses FastAPI + SQLite" |
| `global` | — | User preferences | "Prefer conventional commits" |

`get_context()` aggregates all 4 levels in priority order.

## MCP Tools + Hook Writes

### MCP Tools (low token cost — reads + selective writes)

| Tool | Description |
|---|---|
| `get_context` | Aggregate context from all scopes, ranked by salience (also auto-injected at session start) |
| `save_memory` | Save a memory with scope, type, and auto-resolved context (returns its `id`) |
| `search_memory` | Search your curated memories — scope/type/tags-aware, returns `id`s |
| `search_conversations` | Broad full-text/semantic search across archived transcripts |
| `read_memory` | Fetch full content by memory `id` or conversation `path` |
| `memory_stats` | Database statistics |
| `memory_handoff_begin` | Create handoff for next agent |
| `memory_handoff_accept` | Peek at the pending handoff (non-destructive; the hook consumes it) |
| `memory_pin` | Pin a memory (exempt from decay) |
| `memory_unpin` | Unpin a memory |
| `memory_forget_sweep` | Sweep stale memories |

### Hook writes (zero LLM tokens)

| Hook kind | Description |
|---|---|
| `session-end` with `messages` | Archives full conversation to .md + auto-handoff |
| `log` | Quick session log (creates session-scoped memory) |
| `session-start` | Records session start observation |
| `user-prompt` / `post-tool-use` / `pre-compact` | Lifecycle observations |

## Web UI

When running in HTTP mode (`MCP_TRANSPORT=streamable-http`), a read-only web UI is available:

- `/` — Dashboard with stats and recent memories
- `/projects` — List of projects with memory counts
- `/project/{id}` — Project detail with memories
- `/memory/{id}` — Single memory detail
- `/search` — Full-text search with scope/type filters
- `/audit` — Audit log of all mutations

## Documentation

- [docs/install.md](docs/install.md) — Detailed per-agent install instructions
- [docs/usage.md](docs/usage.md) — Usage guide, hooks, and workflows
- [AGENTS.md](AGENTS.md) — Architecture and developer reference

## Development

```bash
git clone https://github.com/cccadet/myMem0ry.git
cd myMem0ry
bin/setup
uv run python -m pytest
uv run ruff check .
```

## License

[MIT](LICENSE)
