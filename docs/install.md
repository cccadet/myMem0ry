# Installation Guide

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager (installs Python too)
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) on PATH
- spaCy model: `en_core_web_lg` (auto-installed by `mymem0ry doctor`)

## Quick install (PyPI)

No clone needed. Just run the one-liner for your agent:

```bash
# Claude Code
claude mcp add --scope user mymem0ry -- mymem0ry-mcp

# Codex CLI
codex mcp add mymem0ry -- mymem0ry-mcp

# VS Code
code --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'

# Cursor
cursor --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
```

Or use the installer (auto-detects your agent):

```bash
git clone https://github.com/cccadet/myMem0ry.git && cd myMem0ry
bin/install.sh
```

After installing the MCP server, download the spaCy model:

```bash
mymem0ry doctor       # auto-downloads spaCy model if missing
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

For **HTTP** transport (used by Cursor remote, Docker):
```bash
MCP_TRANSPORT=streamable-http MCP_PORT=49374 mymem0ry-mcp
```

## Option 2: Docker

```bash
docker compose -f docker/docker-compose.yml up -d
curl http://127.0.0.1:49374/health
```

The server exposes:
- `GET /health` — health check
- MCP protocol on `/mcp` (when using streamable-http transport)

### Docker data

All data lives in `/data` inside the container, mounted as a Docker volume:

```
/data/
├── conversations/    # .md conversation files
│   └── .vec.db       # sqlite-vec embeddings index
└── memories.db       # SQLite structured memories
```

To back up:
```bash
docker run --rm -v mymem0ry-data:/data -v $(pwd):/backup alpine \
    tar czf /backup/mymem0ry-backup.tar.gz -C /data .
```

---

## Agent setup (detailed)

### Claude Code

**One-liner:**
```bash
claude mcp add --scope user mymem0ry -- mymem0ry-mcp
```

**Or manual config** — add to `~/.claude/settings.json`:

```json
  "mcpServers": {
    "mymem0ry": {
      "command": "mymem0ry-mcp"
    }
  }
```

**Hooks (optional, for auto-capture):** Use the new command to get the correct path:

```bash
mymem0ry hooks --config        # Print settings.json snippet with correct paths
mymem0ry hooks --path          # Just print the hooks directory
```

Then copy the snippet into `~/.claude/settings.json`.

**Or manual config** — add to `~/.claude/settings.json`:

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

> Replace `/path/to/myMem0ry/` with the output of `mymem0ry hooks --path`.

### OpenCode

**Manual config** — add to your `opencode.json`:

```json
{
  "mcp": {
    "mymem0ry": {
      "type": "local",
      "command": ["mymem0ry-mcp"],
      "enabled": true
    }
  }
}
```

**Hooks (optional):** Copy `hooks/opencode/mymem0ry-hook.sh` to your project's `.opencode/hooks/` directory.

### Codex CLI

**One-liner:**
```bash
codex mcp add mymem0ry -- mymem0ry-mcp
```

**Or manual config** — add to `~/.codex/config.toml`:

```toml
[mcp_servers.mymem0ry]
command = "mymem0ry-mcp"
```

**Hooks (optional):** Copy `hooks/codex/mymem0ry-hook.sh` to `~/.codex/hooks/`.

### Cursor

**One-liner (stdio):**
```bash
cursor --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
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
code --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
```

**Or workspace config** — add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "mymem0ry": {
      "command": "mymem0ry-mcp"
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
      "command": "mymem0ry-mcp"
    }
  }
}
```

---

## Storage location

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

### Custom storage

Override with environment variables (or `.env` file):

```bash
export DB_PATH=/path/to/shared/memories.db
export CONVERSATIONS_DIR=/path/to/shared/conversations
export VECTOR_DB_PATH=/path/to/shared/conversations/.vec.db
```

| Variable | Default | Purpose |
|---|---|---|
| `CONVERSATIONS_DIR` | `data/conversations` | .md conversation files |
| `DB_PATH` | `data/memories.db` | SQLite memories database |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec index |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model for embeddings and search |
| `MCP_TRANSPORT` | `stdio` | MCP transport: `stdio`, `sse`, `streamable-http` |
| `MEM0RY_HOST` | `127.0.0.1` | Host for HTTP transport |
| `MEM0RY_PORT` | `49374` | Port for HTTP transport |

### Language support

Default is English. For Portuguese:

```bash
export SPACY_MODEL=pt_core_news_lg
mymem0ry doctor       # auto-downloads the model
```

Any spaCy model works — set `SPACY_MODEL` and run `mymem0ry doctor`.

### Importing existing conversations

```bash
mymem0ry split data/openai/export     # ChatGPT
mymem0ry split data/gemini            # Gemini
mymem0ry split data/claude            # Claude
mymem0ry split                        # Auto-detect all
mymem0ry index                        # Build search indexes
mymem0ry migrate --reprocess          # Migrate into structured memories
```

### DoltLite sync (experimental)

For cross-machine memory sync, myMem0ry supports [DoltLite](https://github.com/dolthub/doltlite) as a version-controlled backend for the memories DB.

Requirements:

- Python with `_sqlite3` as a shared extension (Homebrew, distro, pyenv, conda). It does **not** work with `uv python install`.
- `pip install doltlite`

Setup:

```bash
export MEM0RY_SYNC_ENGINE=doltlite
export MEM0RY_SYNC_REMOTE=file:///path/to/shared/remote.doltlite
mymem0ry sync init --remote $MEM0RY_SYNC_REMOTE
mymem0ry sync push
```

Remote types:

- `file://` — shared folder / synced cloud drive.
- `http://` / `https://` — DoltLite remote server.

Full cross-machine workflow:

1. Sync the memories DB via DoltLite:
   ```bash
   mymem0ry sync push   # on machine A
   mymem0ry sync pull   # on machine B
   ```
2. Sync conversation files and indexes via git:
   ```bash
   cd data
   git init
   git remote add origin https://github.com/you/my-mem0ry-data
   git add .
   git commit -m "initial data"
   git push
   ```
3. On a new machine:
   ```bash
   git clone https://github.com/you/my-mem0ry-data.git data
   mymem0ry sync init --remote $MEM0RY_SYNC_REMOTE
   mymem0ry sync pull
   mymem0ry index --backend vector
   ```

Resolve DoltLite conflicts keeping the local version:

```bash
sqlite3 $DB_PATH "SELECT dolt_conflicts_resolve('--ours', 'memories');"
sqlite3 $DB_PATH "SELECT dolt_commit('-m', 'resolve conflict');"
```
