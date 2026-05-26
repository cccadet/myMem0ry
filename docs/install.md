# Installation Guide

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager (installs Python too)
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) on PATH
- spaCy model: `pt_core_news_lg` (auto-installed)

## Quick install (PyPI)

No clone needed. Just run the one-liner for your agent:

```bash
# VS Code
code --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'

# Cursor
cursor --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'

# Claude Code
claude mcp add --scope user mymem0ry -- uvx mymem0ry-mcp

# Codex CLI
codex mcp add mymem0ry -- uvx mymem0ry-mcp

# OpenCode — add to opencode.json:
#   "mcpServers": { "mymem0ry": { "command": "uvx", "args": ["mymem0ry-mcp"] } }
```

Or use the installer (auto-detects your agent):

```bash
git clone https://github.com/cccadet/myMem0ry.git && cd myMem0ry
bin/install.sh
```

## Option 1: Local install with uv

```bash
git clone https://github.com/cccadet/myMem0ry.git
cd myMem0ry
bin/setup
uv run pytest
```

### Start the MCP server

For **stdio** transport (used by Claude Code, OpenCode, Codex):
```bash
mymem0ry-mcp
```

For **HTTP** transport (used by hooks, Cursor, remote access):
```bash
MCP_TRANSPORT=streamable-http MCP_PORT=49374 mymem0ry-mcp
```

## Option 2: Docker

```bash
docker compose -f docker/docker-compose.yml up -d
curl http://127.0.0.1:49374/health
```

The server exposes:
- `POST /hook` — lifecycle hook endpoint
- `GET /health` — health check
- MCP protocol on `/mcp` (when using streamable-http transport)

### Data directory

All data lives in `/data` inside the container, mounted as a Docker volume:

```
/data/
├── conversations/    # .md conversation files
├── memories.db       # SQLite structured memories
└── conversations/
    └── .vec.db       # sqlite-vec embeddings index
```

To back up:
```bash
docker run --rm -v mymem0ry-data:/data -v $(pwd):/backup alpine \
    tar czf /backup/mymem0ry-backup.tar.gz -C /data .
```

To restore:
```bash
docker run --rm -v mymem0ry-data:/data -v $(pwd):/backup alpine \
    sh -c "cd /data && tar xzf /backup/mymem0ry-backup.tar.gz"
```

---

## Agent setup (detailed)

### Claude Code

**One-liner:**
```bash
claude mcp add --scope user mymem0ry -- uvx mymem0ry-mcp
```

**Or manual config** — add to `~/.claude/settings.json`:

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

**Hooks (optional, for auto-capture):** Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "command": "/path/to/myMem0ry/hooks/claude-code/session-start.sh"
    }],
    "PostToolUse": [{
      "command": "/path/to/myMem0ry/hooks/claude-code/mymem0ry-hook.sh PostToolUse"
    }]
  }
}
```

### OpenCode

**Manual config** — add to your `opencode.json`:

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

**Hooks (optional):** Copy `hooks/opencode/mymem0ry-hook.sh` to your project's `.opencode/hooks/` directory.

### Codex CLI

**One-liner:**
```bash
codex mcp add mymem0ry -- uvx mymem0ry-mcp
```

**Or manual config** — add to `~/.codex/config.toml`:

```toml
[mcp_servers.mymem0ry]
command = "uvx"
args = ["mymem0ry-mcp"]
```

**Hooks (optional):** Copy `hooks/codex/mymem0ry-hook.sh` to `~/.codex/hooks/`.

### Cursor

**One-liner (stdio):**
```bash
cursor --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'
```

**Or HTTP mode** — start the server first:

```bash
MCP_TRANSPORT=streamable-http mymem0ry-mcp
```

Then add to Cursor Settings → MCP:

```json
{
  "mymem0ry": {
    "url": "http://127.0.0.1:49374/mcp"
  }
}
```

### VS Code

**One-liner:**
```bash
code --add-mcp '{"name":"mymem0ry","command":"uvx","args":["mymem0ry-mcp"]}'
```

**Or workspace config** — add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "mymem0ry": {
      "command": "uvx",
      "args": ["mymem0ry-mcp"]
    }
  }
}
```

### Gemini CLI

**Manual config** — add to Gemini CLI MCP configuration:

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

---

## Data directory (local install)

By default, data lives in `data/` inside the project root:

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

| Variable | Default | Purpose |
|---|---|---|
| `CONVERSATIONS_DIR` | `data/conversations` | .md conversation files |
| `DB_PATH` | `data/memories.db` | SQLite memories database |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |

### Ingesting existing conversations

```bash
mymem0ry split data/openai/export     # ChatGPT
mymem0ry split data/gemini            # Gemini
mymem0ry split data/claude            # Claude
mymem0ry split                        # Auto-detect all
mymem0ry index                        # Build search indexes
mymem0ry migrate --reprocess          # Migrate into structured memories
```
