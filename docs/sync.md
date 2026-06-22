# Cross-machine sync

myMem0ry is local-first and does not require a cloud service, but you can synchronize your memories across multiple machines. The recommended approach is to keep the `data/` directory in a **private git repository** and let myMem0ry pull and push automatically.

> **TL;DR**
> - Keep `data/` in a git repository with a remote.
> - Set `MEM0RY_GIT_AUTO_SYNC=1`.
> - myMem0ry pulls before reads and pushes after writes.

## How it works

When git auto-sync is enabled:

- **Before every `get_context()` call:** myMem0ry runs `git pull --rebase` in the data directory so the agent always sees the latest memories.
- **After every memory write** (create, update, delete, restore): myMem0ry runs `git add -A`, `git commit`, and `git push` so changes are propagated to other machines.
- **Failures are logged, never fatal.** A network or git problem will not break the agent; it will just retry on the next operation.

> **Warning:** git auto-sync is `last-write-wins`. If you edit on two machines before a sync runs, you may get a conflict or one machine's changes will be overwritten. It is designed for **single-user, sequential workflows**.

## What gets synchronized

The git repository should cover the entire `data/` directory:

- `memories.db` — structured memories, observations, handoffs, audit log.
- `conversations/**/*.md` — archived conversations.
- `conversations/.vec.db` — vector search index (`sqlite-vec`).
- Optional: raw exports in `data/openai/`, `data/gemini/`, `data/claude/`, etc.

Add these to `.gitignore`:

```gitignore
*.pid
spool/
```

## Setup

### 1. Initialize the git repository

```bash
cd data
git init
git remote add origin https://github.com/you/my-mem0ry-data.git
cat > .gitignore <<'EOF'
*.pid
spool/
EOF
git add .
git commit -m "initial myMem0ry data"
git push -u origin main
```

### 2. Enable auto-sync

```bash
export MEM0RY_GIT_AUTO_SYNC=1
```

Optional configuration:

| Variable | Default | Purpose |
|---|---|---|
| `MEM0RY_GIT_AUTO_SYNC` | `0` | Set to `1` to enable automatic pull/push. |
| `MEM0RY_GIT_SYNC_DIR` | parent of `DB_PATH` | Directory that contains the `.git` repo. |
| `MEM0RY_GIT_SYNC_REMOTE` | `origin` | Remote name. |
| `MEM0RY_GIT_SYNC_BRANCH` | `main` | Branch to pull/push. |

### 3. On a new machine

```bash
# Clone the data repository into the project.
git clone https://github.com/you/my-mem0ry-data.git data

# Rebuild search indexes if the .md files changed.
mymem0ry index --backend vector
```

## Daily workflow

On machine A after working:

```bash
mymem0ry git-sync status
mymem0ry git-sync push
```

The push is usually unnecessary because auto-sync already pushed after each write, but it is useful if you changed files manually.

On machine B before continuing:

```bash
mymem0ry git-sync pull
```

Again, this is usually automatic when the agent calls `get_context()`.

## Manual commands

```bash
mymem0ry git-sync status   # show repo status
mymem0ry git-sync pull     # pull latest changes
mymem0ry git-sync push     # commit and push local changes
```

## Conflict resolution

If `mymem0ry git-sync pull` reports a conflict, resolve it manually with git:

```bash
cd data
# Decide which version to keep, then:
git add .
git rebase --continue
mymem0ry git-sync push
```

For `memories.db` conflicts, pick one version and discard the other — SQLite binaries cannot be merged.

## When not to use git auto-sync

- **Single machine:** you do not need sync at all.
- **Multiple users editing simultaneously:** use a real database replication solution instead.
- **You only need occasional backups:** use `mymem0ry backup --to file.tar.gz` and `mymem0ry restore --from file.tar.gz`.

## Alternatives

- **Syncthing / Dropbox / iCloud Drive / rsync:** synchronize the `data/` directory through a file-sync service. Simpler, but make sure myMem0ry is not running while files are syncing to avoid SQLite corruption.
- **Manual git workflow:** manage `data/` with git yourself, without auto-sync.
