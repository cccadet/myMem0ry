# Usage Guide

## Switching harness mid-task

The core use case: stop in one agent, continue in another in the same directory.
It works because every agent resolves the same scopes from `cwd` (git remote =
project, git branch = context), and a **handoff** carries the "where we left off".

End-to-end flow:

1. **Set up every agent once** — add the `mymem0ry-mcp` MCP server and the
   lifecycle hooks (see [install.md](install.md)). The MCP server auto-starts the
   shared HTTP server; all agents talk to the same SQLite DB.
2. **Work in agent A** (e.g. Claude Code). Save decisions with `save_memory`
   (`scope=project`/`context`). At the end, the `session-end` hook creates a
   handoff automatically from the session's observations — or call
   `memory_handoff_begin(summary=..., open_questions=[...], next_steps=[...])`
   for a curated one.
3. **Open agent B** (e.g. Codex, OpenCode) in the same directory. Its
   `session-start` hook fetches the pending handoff and prepends it to the first
   prompt; the agent can also call `memory_handoff_accept` or `get_context`.
4. Continue. `search_memory` + `read_memory` retrieve full past records.

Notes:

- **Same directory matters** — scopes resolve from the git remote and branch, so
  agent B must run in the same repo/branch to see project/context memories.
- **Stable session id** — the shipped Claude Code hooks read the real
  `session_id` from the hook payload. If you wire hooks manually for another
  agent, pass a session id that is consistent across that agent's
  start/tool/end events (or set `MYMEM0RY_SESSION_ID`), otherwise the auto
  handoff has no observations to summarize.
- A handoff is accepted once (single latest, per project) and expires after 7 days.

## How memory works

myMem0ry uses a 4-level scope hierarchy, resolved automatically from the current working directory:

1. **global** — User preferences, patterns. Available everywhere.
2. **project** — Tied to a git remote URL. Architecture decisions, tech stack.
3. **context** — Tied to a git branch. Branch-specific decisions.
4. **session** — Ephemeral. Current session state, logs.

When an agent calls `get_context()`, it aggregates memories from all 4 levels in priority order (session first, global last).

### Example: multi-branch project

```
Project: github.com/acme/webapp
├── global: "User prefers conventional commits"
├── project: "FastAPI + SQLite, auth via JWT"
├── context (main): "Stable, production branch"
├── context (feat/payments): "Integrating Stripe, API v2024"
└── session: "Currently debugging webhook signature validation"
```

## Lifecycle hooks

Hooks run CLI commands directly — no HTTP server needed. They work with both stdio and HTTP MCP transports.

### What hooks do

| Event | Hook script | CLI command |
|---|---|---|
| Session start | `session-start.sh` | `mymem0ry context` — loads context, prints to stdout |
| Session end | `session-end.sh` | `mymem0ry save` — saves session summary |
| Tool use / message | `mymem0ry-hook.sh` | `mymem0ry log` — logs event to session memory |

### Install hooks

**Claude Code:**

Run this to get the correct paths for your install:

```bash
mymem0ry hooks --config
```

Then add the printed snippet to `~/.claude/settings.json`. Example:

```json
{
  "hooks": {
    "SessionStart": [{"command": "/path/to/hooks/claude-code/session-start.sh"}],
    "PostToolUse": [{"command": "/path/to/hooks/claude-code/mymem0ry-hook.sh PostToolUse"}]
  }
}
```

**Other agents:** Hook scripts are in `hooks/<agent>/`. Copy and configure per agent documentation.

### How session-start works

The `session-start` hook calls `mymem0ry context --cwd $CWD` which:

1. Resolves git context (project_id, branch)
2. Queries memories across all scopes
3. Prints results to stdout

Claude Code (and similar agents) prepend hook stdout to the conversation. The agent sees your project context before the first prompt.

## Using the MCP tools

Once the MCP server is configured, agents can call these tools:

### Save important information

```
> We decided to use SQLite instead of Postgres for this project.

(Agent calls save_memory with scope=project, memory_type=decision)
```

### Ask about past decisions

```
> What did we decide about the database?

(Agent calls search_memory or get_context to find the decision)
```

### Continue from where you left off

```
> Where did we leave off?

(Agent calls get_context to load session/project context)
```

## Search backends

| Backend | How it works | When to use |
|---|---|---|
| `ripgrep` (default) | Fast text search via ripgrep | Quick lookups, no index needed |
| `bm25` | BM25Okapi ranking | Better relevance ranking |
| `fts5` | SQLite FTS5 | Fast full-text search |
| `hybrid` | RRF fusion of BM25 + vector | Best recall, needs vector index |

### Build indexes

```bash
mymem0ry index                  # All backends
mymem0ry index --backend bm25   # BM25 only
mymem0ry index --backend fts5   # FTS5 only
mymem0ry index --backend vector # Vector (spaCy) only
```

### Semantic query expansion

Add `--expand` to any search to expand the query with semantically related tokens:

```bash
mymem0ry search "database" --expand
# Expands to: database, storage, sqlite, postgres, ...
```

## Importing conversations

### Supported formats

| Source | Format | Detection |
|---|---|---|
| ChatGPT | JSON (`convs.json`) | `mapping` key with `node` structure |
| Gemini | JSON Takeout | `safeHtmlItem` or `text` entries |
| Claude Code | JSONL logs | Per-message JSON lines |
| Claude Export | JSON | `chat_messages` array |

### Import workflow

```bash
# 1. Place exports in default locations or specify path
cp chatgpt-export.zip data/openai/export/
# or
mymem0ry split --source /path/to/export

# 2. Split into .md files (auto-detects format)
mymem0ry split

# 3. Build search indexes
mymem0ry index

# 4. Migrate into structured memories
mymem0ry migrate

# 5. Verify
mymem0ry stats
mymem0ry doctor
```

### Force specific parser

```bash
mymem0ry split --source data/openai --type openai
mymem0ry split --source data/gemini --type gemini
mymem0ry split --source data/claude --type claude-code
mymem0ry split --source data/claude-export --type claude-export
```

## Memory maintenance

### Decay old sessions

Session-scoped `log` memories are automatically candidates for decay. Project/global memories are never auto-deleted.

```bash
# Preview what would be deleted
mymem0ry decay --days 90 --dry-run

# Delete session logs older than 90 days with no access
mymem0ry decay --days 90
```

### Re-ingest from scratch

```bash
mymem0ry migrate --reprocess    # Drops DB, reingests all .md files into v3 schema
```

## Language support

myMem0ry uses spaCy for embeddings and semantic search. The default model is English (`en_core_web_lg`).

For Portuguese:

```bash
export SPACY_MODEL=pt_core_news_lg
mymem0ry doctor       # auto-downloads the model
```

Any spaCy model works — set `SPACY_MODEL` and run `mymem0ry doctor`.
