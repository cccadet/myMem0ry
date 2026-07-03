# Operations Guide

This page covers the CLI commands you use to operate myMem0ry day-to-day.

## Context and saving

### `mymem0ry context [--cwd <path>]`

Prints the most relevant memories for the current directory. Resolves git remote → `project_id`, git branch → `context`, and loads session/context/project/global in priority order. This is what the `session-start` hook runs.

Source: `src/mem0ry/cli/memory.py`, backed by `src/mem0ry/db/store_memories/context.py`.

### `mymem0ry save [--cwd <path>]`

Saves a session summary. Typically called by the `session-end` hook. Internally calls `end_session` + `create_memory` with `scope=session`.

### `mymem0ry log`

Logs an observation to the `observations` table. Called by the per-message hook for mutating tool events.

## Migration

### `mymem0ry migrate`

Converts legacy `.md` conversation exports into structured SQLite memories. Safe to re-run; it skips already-imported files.

### `mymem0ry migrate --reprocess`

**Destructive.** Drops the database and re-ingests everything from scratch. Use when schema changes make old data incompatible.

Source: `src/mem0ry/cli/migration.py`, `src/mem0ry/db/migrate.py`.

## Dataset builder

### `mymem0ry dataset`

Builds a ChatML JSONL training dataset from exported OpenAI conversations. The pipeline:

1. Parse `data/openai/export/` (or `CONVERSATIONS_DIR`)
2. Build overlapping ChatML chunks (`builder.py`)
3. Apply quality filters, deduplicate, temporal enrichment
4. Train/validation split (default 5% val)
5. Write `output/chatml.jsonl` + stats

Source: `src/mem0ry/cli/memory.py`, `src/mem0ry/pipeline/dataset.py`, `src/mem0ry/dataset/`.

## Retention and cleanup

### `mymem0ry decay [--days 90] [--dry-run]`

Recomputes salience scores for all memories. Usually run before `forget-sweep`.

### `mymem0ry forget-sweep [--execute/--dry-run]`

Soft-deletes low-salience memories and hard-deletes expired ones. Pinned memories are always exempt.

### `mymem0ry pin <memory_id>` / `mymem0ry unpin <memory_id>`

Pinning exempts a memory from decay. Facts and decisions are pinned by default at creation time.

Source: `src/mem0ry/db/retention.py`, `src/mem0ry/cli/retention.py`.

## Backup and restore

### `mymem0ry backup --to <file.tar.gz>`

Creates a compressed archive of `data/` (database + conversations + memories).

### `mymem0ry restore --from <file.tar.gz>`

Restores `data/` from a backup archive. Overwrites existing files.

Source: `src/mem0ry/cli/backup.py`.

## Git sync

### `mymem0ry git-sync status`

Shows whether the data directory is a git repo, current branch, and unpushed commits.

### `mymem0ry git-sync pull`

Runs `git pull --rebase` in the data directory.

### `mymem0ry git-sync push`

Runs `git add -A`, `git commit`, `git push`.

Source: `src/mem0ry/cli/git_sync.py`, `src/mem0ry/db/git_sync.py`.

## Server control

### `mymem0ry serve [--host] [--port] [--detach]`

Starts the HTTP server manually. When `--detach` is used, the server runs as a background daemon and writes a PID file.

The MCP server usually auto-starts the HTTP daemon, so you rarely need this.

Source: `src/mem0ry/cli/server.py`, `src/mem0ry/daemon.py`.

## Diagnostics

### `mymem0ry doctor`

Runs a 6-check diagnostic:
1. Python version
2. `mymem0ry` on PATH
3. spaCy model installed (auto-downloads if missing)
4. SQLite + `sqlite-vec` loadable
5. `ripgrep` on PATH
6. Database directory writable

### `mymem0ry version`

Shows installed version and latest PyPI release.

### `mymem0ry stats`

Counts memories, observations, handoffs, and projects.

### `mymem0ry projects`

Lists all known projects with memory counts.

Source: `src/mem0ry/cli/diagnostics.py`.

## Search backends (conversation search)

### `mymem0ry search <query> [--backend <name>]`

Search archived conversations with the selected backend. Valid backends: `db`, `ripgrep`, `fts`, `bm25`, `vector`, `hybrid`.

### `mymem0ry index --backend <name>`

Rebuilds the chosen index (BM25, FTS5, or vector) from the conversation directory.

Source: `src/mem0ry/cli/conversation.py`, `src/mem0ry/conversations/search_*.py`.
