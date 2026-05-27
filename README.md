# myMem0ry

> Personal memory for AI coding agents. Offline. Zero API keys. Works with any agent.

[![CI](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml/badge.svg)](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml)

## What it does

Persistent memory that any AI agent can read and write. Quit Claude Code mid-task, open Codex in the same directory — it picks up where you left off.

- **Scoped memory**: session → context (branch) → project → global
- **Cross-agent handoffs**: typed handoff records with summary, open questions, next steps
- **Auto-resolves context** from `cwd` (git branch, remote URL)
- **Semantic search**: spaCy + sqlite-vec + BM25/FTS5/hybrid RRF fusion
- **Lifecycle hooks**: fire-and-forget HTTP endpoint, payload sanitization, immutable observations
- **Retention**: salience-based decay with tiers (working/procedural/semantic), pin/unpin
- **Auth**: Bearer token, host allowlisting, CORS (for HTTP transport)
- **Web UI**: dark mode read-only viewer (dashboard, projects, search, audit log)
- **Backup/restore**: tarball CLI commands

## Install

### Prerequisites

```bash
pip install uv        # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install mymem0ry-mcp
mymem0ry doctor       # checks + auto-installs spaCy model
```

For Portuguese: set `SPACY_MODEL=pt_core_news_lg` in `.env` before running `mymem0ry doctor`.

**Zero config**: after install, just add the MCP server + hooks to your agent config below.
The HTTP server auto-starts when the MCP server runs — no separate `serve` command needed.

### Claude Code

```bash
claude mcp add --scope user mymem0ry -- uvx mymem0ry-mcp
```

### OpenCode

Add to `~/.config/opencode/opencode.json` (global) or `./opencode.json` (project):

```json
{
  "mcp": {
    "mymem0ry": {
      "type": "local",
      "command": ["uvx", "mymem0ry-mcp"],
      "enabled": true
    }
  },
  "hooks": {
    "session-start": "curl -s -m 2 -X POST http://127.0.0.1:49374/hook -H 'Content-Type: application/json' -d '{\"kind\":\"session-start\",\"session_id\":\"'$OPENCODE_SESSION_ID'\",\"agent\":\"opencode\",\"cwd\":\"'$PWD'\"}' > /dev/null 2>&1",
    "session-end": "curl -s -m 2 -X POST http://127.0.0.1:49374/hook -H 'Content-Type: application/json' -d '{\"kind\":\"session-end\",\"session_id\":\"'$OPENCODE_SESSION_ID'\",\"agent\":\"opencode\",\"cwd\":\"'$PWD'\"}' > /dev/null 2>&1"
  }
}
```

The hooks POST lifecycle events to `POST /hook` (fire-and-forget, 2s timeout).
No manual server start needed — the HTTP server auto-starts when the MCP server runs (e.g., when your agent starts).

### Claude Code

MCP + hooks em `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "mymem0ry": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mymem0ry-mcp"]
    }
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "~/.local/share/mymem0ry/hooks/claude-code/session-start.sh"}]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "~/.local/share/mymem0ry/hooks/claude-code/session-end.sh"}]
      }
    ]
  }
}
```

Os scripts de hook: `~/.local/share/mymem0ry/hooks/claude-code/session-start.sh` e `session-end.sh`.
Eles recebem o payload completo no stdin (incluindo `messages` no session-end) e encaminham para `POST /hook`.

### Codex CLI

```bash
codex mcp add mymem0ry -- uvx mymem0ry-mcp
```

### VS Code

```bash
code --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mym0ry-mcp"]}'
```

### Cursor

```bash
cursor --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'
```

### Gemini CLI

Same stdio pattern. Add to Gemini CLI MCP config with `command: uvx` and `args: ["mymem0ry-mcp"]`.

### Docker

```bash
docker compose -f docker/docker-compose.yml up -d
curl http://127.0.0.1:49374/health
```

For detailed per-agent instructions (manual config, HTTP mode): [docs/install.md](docs/install.md)

### Lifecycle Hooks (per-agent setup)

Lifecycle hooks POST to `POST /hook` on the myMem0ry HTTP server.
The server auto-starts when the MCP server runs — no manual `serve` step needed.

| Agent | Lifecycle hooks | How it works |
|---|---|---|
| **OpenCode** | ✅ Nativo | `hooks` em `opencode.json` com `$OPENCODE_SESSION_ID` (ver acima) |
| **Claude Code** | ✅ Nativo | `hooks` em `~/.claude/settings.json` — scripts recebem payload completo no stdin, incluindo `messages` no session-end |
| **Codex CLI** | ✅ Hook scripts | `codex hook add session-end ./hook-session-end.sh` |
| **Genérico** | — | `curl -X POST http://127.0.0.1:49374/hook -H 'Content-Type: application/json' ...` |

Hook payload fields:

| Field | Required | Description |
|---|---|---|
| `kind` | yes | `session-start`, `session-end`, `log`, `user-prompt`, `post-tool-use`, `pre-compact` |
| `session_id` | yes | Unique session identifier (max 64 chars) |
| `agent` | no | `opencode`, `claude-code`, `codex`, `manual`, `hook` (max 64 chars) |
| `cwd` | no | Working directory for context resolution (max 512 chars) |
| `title` | no | Short label (max 500 chars) |
| `body` | no | Content (max 10 000 chars) |
| `messages` | no (session-end) | `[{"role": "user"\|"assistant", "content": "..."}]` — archived as .md |

All payloads are sanitized: secrets (API keys, tokens, Bearer) are redacted, home paths are stripped, and fields are truncated to max lengths.

## Configuration

All via environment variables (or `.env` file in the project root):

| Variable | Default | Description |
|---|---|---|
| `CONVERSATIONS_DIR` | `data/conversations` | Where `.md` conversation files are stored |
| `DB_PATH` | `data/memories.db` | SQLite memories database |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model for embeddings and search |
| `MEM0RY_HOST` | `127.0.0.1` | Host for HTTP transport |
| `MEM0RY_PORT` | `49374` | Port for HTTP transport |
| `MEM0RY_TOKEN` | _(empty)_ | Bearer token for HTTP auth (skip = no auth) |
| `MEM0RY_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Host allowlist (DNS rebinding protection) |
| `MEM0RY_CORS_ORIGINS` | _(empty)_ | CORS origins for web UI |

### Custom storage location

```bash
export DB_PATH=/path/to/shared/memories.db
export CONVERSATIONS_DIR=/path/to/shared/conversations
```

For Portuguese language support:

```bash
export SPACY_MODEL=pt_core_news_lg
mymem0ry doctor       # auto-downloads the model
```

## Import conversations

myMem0ry auto-detects the format. Supports ChatGPT, Gemini, and Claude exports.

```bash
# Auto-detect from default locations (data/openai, data/gemini, data/claude)
mymem0ry split

# Specific source
mymem0ry split --source path/to/chatgpt-export
mymem0ry split --source path/to/gemini-takeout
mymem0ry split --source path/to/claude-export

# Force parser type
mymem0ry split --source path/to/data --type openai
mymem0ry split --source path/to/data --type gemini
mymem0ry split --source path/to/data --type claude-code

# Then build indexes and migrate to structured memory
mymem0ry index
mymem0ry migrate
```

## CLI commands

```bash
# Context & search
mymem0ry context --cwd .                    # Load context for current project
mymem0ry save "Title" "Content" --scope project  # Save a memory
mymem0ry log "message"                      # Quick session log
mymem0ry search "query"                     # ripgrep search
mymem0ry search "query" --backend hybrid --expand
mymem0ry index                              # Build BM25 + FTS5 + vector indexes
mymem0ry migrate --reprocess                # Reingest into latest schema

# Overview
mymem0ry stats                              # Database overview
mymem0ry projects                           # List projects with memories
mymem0ry doctor                             # System health check

# Retention
mymem0ry decay --days 90 --dry-run          # Preview decay
mymem0ry pin <memory_id>                    # Pin memory (exempt from decay)
mymem0ry unpin <memory_id>                  # Unpin memory
mymem0ry forget-sweep --dry-run             # Preview salience-based sweep

# Handoffs
mymem0ry handoff begin --summary "..."      # Create handoff for next agent
mymem0ry handoff accept                     # Accept pending handoff
mymem0ry handoff status                     # Check server status

# Server & backup
mymem0ry serve                              # Start HTTP server (MCP + hooks + handoffs + web UI)
mymem0ry serve --detach                     # Start in background (daemon mode)
mymem0ry backup --to backup.tar.gz          # Backup DB + conversations
mymem0ry restore --from backup.tar.gz       # Restore from backup

# Other
mymem0ry benchmark "query"                  # Compare search backends
mymem0ry expand "token"                     # Semantically related tokens
mymem0ry dataset                            # ChatML JSONL (legacy)
mymem0ry observe session-start              # Send lifecycle observation
```

## Memory scopes

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
| `get_context` | Aggregate context from all scopes |
| `save_memory` | Save a memory with scope, type, and auto-resolved context |
| `search_memory` | Search with semantic query expansion |
| `memory_stats` | Database statistics |
| `memory_handoff_begin` | Create handoff for next agent |
| `memory_handoff_accept` | Accept pending handoff |
| `memory_pin` | Pin a memory (exempt from decay) |
| `memory_unpin` | Unpin a memory |
| `memory_forget_sweep` | Sweep stale memories (preview or execute) |

### Hook writes (zero LLM tokens)

| Hook kind | Description |
|---|---|
| `session-end` with `messages` | Archives full conversation to .md + auto-handoff |
| `log` | Quick session log (creates session-scoped memory) |
| `session-start` | Records session start observation |
| `user-prompt` / `post-tool-use` / `pre-compact` | Lifecycle observations |

All writes go through `POST /hook` (fire-and-forget, 2s timeout). Payloads are sanitized (secrets redacted, paths stripped, fields truncated). The LLM never serializes conversations.

The CLI `mymem0ry observe` can also send lifecycle events and supports `MEM0RY_TOKEN` auth.

## Web UI

When running in HTTP mode (`MCP_TRANSPORT=streamable-http`), a read-only web UI is available:

- `/` — Dashboard with stats and recent memories
- `/projects` — List of projects with memory counts
- `/project/{id}` — Project detail with memories
- `/memory/{id}` — Single memory detail
- `/search` — Full-text search with scope/type filters
- `/audit` — Audit log of all mutations
- `/api/memories` — JSON API endpoint

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

MIT
