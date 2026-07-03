# Agent Setup & Workflows

myMem0ry is designed to sit behind an MCP server and capture context automatically through lifecycle hooks. This page covers how to wire it up for day-to-day agent work.

## MCP transport modes

The same `mymem0ry-mcp` binary supports two transports:

### stdio (default)
Used by Claude Code, OpenCode, Codex CLI, Cursor, VS Code.

```bash
mymem0ry-mcp
```

The MCP server starts, auto-launches the HTTP daemon, and stays alive as long as the agent process is connected.

### streamable-http
Used by remote setups, Docker, or when you want to point a browser or curl at the server.

```bash
MCP_TRANSPORT=streamable-http MCP_PORT=49374 mymem0ry-mcp
```

Or via the CLI:

```bash
mymem0ry serve --detach
```

## Installing hooks

Hooks run CLI commands directly; they do **not** require the HTTP server.

1. Print the config snippet for your agent:
   ```bash
   mymem0ry hooks --config
   ```

2. Copy the printed JSON into your agent settings (e.g. `~/.claude/settings.json`).

3. Or install hook scripts to the data directory:
   ```bash
   mymem0ry hooks --install
   ```

Hook scripts live in `hooks/<agent>/` inside the repository. Supported agents: `claude-code`, `opencode`, `codex`, `cursor`, `gemini-cli`.

### What each hook does

| Event | Script | CLI command | Purpose |
|---|---|---|---|
| Session start | `session-start.sh` | `mymem0ry context --cwd $CWD` | Load and print scoped context |
| Session end | `session-end.sh` | `mymem0ry save` | Save a session summary |
| Per-message / tool use | `mymem0ry-hook.sh` | `mymem0ry log` | Log notable events to observations |

Only **mutating tools** (`Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `str_replace_editor`, `create_file`, `apply_patch`) generate observations. Reads are ignored to avoid noise. See `src/mem0ry/hooks/router.py` for the filter logic.

## Scoped memory

Every memory is stored with a **scope** that controls who can see it and when:

| Scope | Key | Example |
|---|---|---|
| `session` | `session_id` | "Currently debugging webhook signature validation" |
| `context` | `context` (git branch) | "Stable, production branch" vs "feat/payments" |
| `project` | `project_id` (git remote) | "FastAPI + SQLite, auth via JWT" |
| `global` | — | "General architecture decisions" |

When an agent calls `get_context()`, the system aggregates in priority order:

1. `session` memories for the current `session_id`
2. `context` memories for the current git branch
3. `project` memories for the current git remote
4. `global` memories (excluding `log` types)

There is no per-scope cap; the `top_k` budget is filled in priority order. Within each scope, rows are ordered by `pinned DESC, salience DESC, created_at DESC`. See `src/mem0ry/db/store_memories/context.py`.

## Cross-agent handoffs

Handoffs let you stop work in one agent and continue in another without losing context.

### Workflow

1. **Agent A** calls `begin_handoff` (or the `session-end` hook does it automatically):
   ```bash
   mymem0ry handoff
   ```
   This creates an open handoff with a summary, open questions, and next steps.

2. **Agent B** sees the handoff:
   ```bash
   mymem0ry handoff status
   ```

3. **Agent B** accepts it:
   ```bash
   mymem0ry handoff accept
   ```
   This marks the handoff `accepted` and returns the full summary to the new session.

Handoffs expire automatically after a configurable period (see `src/mem0ry/db/store_handoffs.py`).

## Git auto-sync (cross-machine)

If you work on multiple machines, keep the `data/` directory in a private git repository and enable auto-sync:

```bash
export MEM0RY_GIT_AUTO_SYNC=1
export MEM0RY_GIT_SYNC_REMOTE=origin
export MEM0RY_GIT_SYNC_BRANCH=main
```

With auto-sync enabled, myMem0ry:
- Runs `git pull --rebase` in the data directory **before** every read.
- Runs `git add -A`, `git commit`, `git push` **after** every write.

Failures are logged, never fatal. For manual control:

```bash
mymem0ry git-sync status
mymem0ry git-sync pull
mymem0ry git-sync push
```

> **Note:** `memories.db` is a binary SQLite file. If it conflicts during sync, keep one copy and discard the other — SQLite binaries cannot be merged.

See `docs/sync.md` and `src/mem0ry/db/git_sync.py` for full details.
