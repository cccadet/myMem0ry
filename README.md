# myMem0ry

> Personal memory for AI agents. Zero API keys. Offline. Pure Python.

[![CI](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml/badge.svg)](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml)

## What it does

- Ingests conversations from ChatGPT, Gemini, Claude → indexed `.md` files
- Semantic search (spaCy + sqlite-vec + BM25/FTS5/hybrid)
- MCP server with scoped memory (session/context/project/global)
- Works with Claude Code, OpenCode, Codex, Cursor, Gemini CLI
- Auto-resolves context from `cwd` (git branch, project, session)
- Docker-ready or local install

## Quick start

### Local

```bash
git clone https://github.com/cccadet/myMem0ry.git
cd myMem0ry
bin/setup

# Ingest conversations
mymem0ry split

# Build indexes
mymem0ry index

# Search
mymem0ry search "python decorators"
mymem0ry search "auth" --backend hybrid --expand

# Start MCP server
mymem0ry-mcp
```

### Docker

```bash
docker compose -f docker/docker-compose.yml up -d
curl http://127.0.0.1:49374/health
```

## Install (one-liner)

Published to PyPI. Works with `uvx` — no clone needed.

```bash
# VS Code
code --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'

# Cursor
cursor --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'

# Claude Code
claude mcp add --scope user mymem0ry -- uvx mymem0ry-mcp

# Codex CLI
codex mcp add mymem0ry -- uvx mymem0ry-mcp

# OpenCode — add to opencode.json manually (see below)
```

Or use the installer script (auto-detects your agent):

```bash
git clone https://github.com/cccadet/myMem0ry.git && cd myMem0ry
bin/install.sh
```

### Manual config

<details>
<summary>Claude Code — <code>~/.claude/settings.json</code></summary>

```json
{
  "mcpServers": {
    "mymem0ry": {
      "command": "uvx",
      "args": ["mymem0ry-mcp"]
    }
  }
}
```
</details>

<details>
<summary>OpenCode — <code>opencode.json</code></summary>

```json
{
  "mcpServers": {
    "mymem0ry": {
      "command": "uvx",
      "args": ["mymem0ry-mcp"]
    }
  }
}
```
</details>

<details>
<summary>Codex CLI — <code>~/.codex/config.toml</code></summary>

```toml
[mcp_servers.mymem0ry]
command = "uvx"
args = ["mymem0ry-mcp"]
```
</details>

<details>
<summary>Cursor / VS Code — HTTP mode</summary>

Start the server first: `MCP_TRANSPORT=streamable-http mymem0ry-mcp`

Then add to Cursor MCP settings:

```json
{
  "mymem0ry": {
    "url": "http://127.0.0.1:49374/mcp"
  }
}
```
</details>

<details>
<summary>Gemini CLI</summary>

Same stdio pattern as Claude Code. Add to Gemini CLI MCP config.
</details>

Full instructions per agent: [docs/install.md](docs/install.md)

## Architecture

```
Conversations (ChatGPT/Gemini/Claude)
        ↓
    [split + ingest]
        ↓
   .md files + embeddings (spaCy 300-dim)
        ↓
   Indexed search (BM25 / FTS5 / sqlite-vec / hybrid RRF)
        ↓
    [MCP Server]
        ↓
   Agents (Claude Code, OpenCode, Codex, Cursor, Gemini CLI)
```

## Memory scopes

Resolved automatically from `cwd`:

| Scope | Identifier | What it stores | Example |
|---|---|---|---|
| `session` | `session_id` (UUID) | Current session context | "Trying to fix auth bug" |
| `context` | git branch / worktree | Decisions for a branch | "On feat/auth, using JWT" |
| `project` | `git remote URL` | Project architecture | "Uses FastAPI + SQLite" |
| `global` | — | User preferences | "Prefer PT-BR commits" |

`get_context()` aggregates all 4 levels: session → context → project → global.

## MCP Tools

| Tool | Description |
|---|---|
| `log_message` | Log a message in the current session |
| `save_memory` | Save a memory with scope, type, and auto-resolved context |
| `save_conversation` | Save a full conversation |
| `read_memory` | Read a memory file's content |
| `search_memory` | Search with semantic query expansion |
| `get_context` | Aggregate context from all scopes (auto-resolves from cwd) |
| `list_scopes` | List scopes with memory counts |
| `end_session` | Mark session as completed |
| `memory_stats` | Database statistics |

## CLI commands

```bash
mymem0ry split                        # Export → .md by date
mymem0ry search "query"               # Search (ripgrep default)
mymem0ry search "query" --backend hybrid --expand
mymem0ry index                        # Build BM25 + FTS5 + vector indexes
mymem0ry migrate                      # .md → SQLite memories
mymem0ry migrate --reprocess          # Drop DB + reingest (v3 schema)
mymem0ry stats                        # Memory database overview
mym0ry projects                       # List projects with memories
mymem0ry doctor                       # System health check
mymem0ry decay [--days 90] [--dry-run]  # Remove old session logs
mymem0ry benchmark "python"           # Compare search backends
mymem0ry expand "france"              # Semantically related tokens
```

## Data directory

```
data/
├── conversations/        # .md files (one per conversation)
│   ├── 2025-01-15/
│   │   ├── abc123.md
│   │   └── def456.md
│   └── .vec.db           # sqlite-vec index
├── memories.db           # SQLite structured memories
└── openai/               # Raw exports (source data)
```

Override with environment variables:

| Variable | Default | Description |
|---|---|---|
| `CONVERSATIONS_DIR` | `data/conversations` | .md conversation files |
| `DB_PATH` | `data/memories.db` | SQLite memories database |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |
| `SPACY_MODEL` | `pt_core_news_lg` | spaCy model for embeddings |
| `MCP_TRANSPORT` | `stdio` | MCP transport: stdio, sse, streamable-http |
| `MCP_HOST` | `127.0.0.1` | Host for HTTP transport |
| `MCP_PORT` | `49374` | Port for HTTP transport |

## Development

```bash
uv sync --group dev
uv run spacy download pt_core_news_lg
uv run python -m pytest
uv run ruff check .
uv run mypy src/mem0ry
```

## License

MIT
