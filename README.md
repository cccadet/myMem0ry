# myMem0ry

> Personal memory for AI coding agents. Offline. Zero API keys. Works with any agent.

[![CI](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml/badge.svg)](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml)

## What it does

Persistent memory that any AI agent can read and write. Quit Claude Code mid-task, open Codex in the same directory — it picks up where you left off.

- Scoped memory: session → context (branch) → project → global
- Auto-resolves context from `cwd` (git branch, remote URL)
- Semantic search (spaCy + sqlite-vec + BM25/FTS5/hybrid)
- CLI hooks for lifecycle events (no server needed)
- MCP server for in-conversation tools

## Install

### Prerequisites

```bash
pip install uv        # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install mymem0ry-mcp
mymem0ry doctor       # checks + auto-installs spaCy model
```

For Portuguese: set `SPACY_MODEL=pt_core_news_lg` in `.env` before running `mymem0ry doctor`.

### Claude Code

```bash
claude mcp add --scope user mymem0ry -- uvx mymem0ry-mcp
```

### OpenCode

Add to `opencode.json`:

```json
{
  "mcp": {
    "mymem0ry": {
      "type": "local",
      "command": ["uvx", "mymem0ry-mcp"],
      "enabled": true
    }
  }
}
```

### Codex CLI

```bash
codex mcp add mymem0ry -- uvx mymem0ry-mcp
```

### VS Code

```bash
code --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'
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

For detailed per-agent instructions (hooks, manual config, HTTP mode): [docs/install.md](docs/install.md)

## Configuration

All via environment variables (or `.env` file in the project root):

| Variable | Default | Description |
|---|---|---|
| `CONVERSATIONS_DIR` | `data/conversations` | Where `.md` conversation files are stored |
| `DB_PATH` | `data/memories.db` | SQLite memories database |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model for embeddings and search |
| `MCP_TRANSPORT` | `stdio` | MCP transport: `stdio`, `sse`, `streamable-http` |
| `MCP_HOST` | `127.0.0.1` | Host for HTTP transport |
| `MCP_PORT` | `49374` | Port for HTTP transport |

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
mymem0ry context --cwd .                    # Load context for current project
mymem0ry save "Title" "Content" --scope project  # Save a memory
mym0ry log "something happened"             # Quick session log
mymem0ry search "query"                     # ripgrep search
mymem0ry search "query" --backend hybrid --expand
mymem0ry index                              # Build BM25 + FTS5 + vector indexes
mymem0ry migrate --reprocess                # Reingest into v3 schema
mymem0ry stats                              # Database overview
mymem0ry projects                           # List projects with memories
mymem0ry doctor                             # System health check
mymem0ry decay --days 90 --dry-run          # Remove old session logs
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

## MCP Tools

| Tool | Description |
|---|---|
| `log_message` | Log a message in the current session |
| `save_memory` | Save a memory with scope, type, and auto-resolved context |
| `save_conversation` | Save a full conversation |
| `read_memory` | Read a memory file's content |
| `search_memory` | Search with semantic query expansion |
| `get_context` | Aggregate context from all scopes |
| `list_scopes` | List scopes with memory counts |
| `end_session` | Mark session as completed |
| `memory_stats` | Database statistics |

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
