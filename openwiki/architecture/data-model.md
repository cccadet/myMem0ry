# Data Model

myMem0ry uses a single SQLite database (default `data/memories.db`) with WAL journal mode and the `sqlite-vec` extension loaded. Schema version is **9**.

## Schema overview

### `memories` — curated memory store

The primary table. Each row is a human- or agent-authored fact, decision, or log entry.

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | 12-char hex UUID |
| `fts_rowid` | `INTEGER UNIQUE` | Stable FTS5 rowid, decoupled from `id` |
| `content` | `TEXT NOT NULL` | Full memory text |
| `scope` | `TEXT NOT NULL DEFAULT 'global'` | `session`, `context`, `project`, `global` |
| `project_id` | `TEXT` | Git remote URL (or `stable_project_id`) |
| `project_path` | `TEXT` | Absolute filesystem path |
| `context` | `TEXT` | Git branch name |
| `session_id` | `TEXT` | Session UUID |
| `memory_type` | `TEXT NOT NULL DEFAULT 'log'` | `log`, `fact`, `pattern`, `decision` |
| `source` | `TEXT NOT NULL DEFAULT 'manual'` | `manual`, `hook`, `import`, `evolve` |
| `tags` | `TEXT NOT NULL DEFAULT '[]'` | JSON array string |
| `title` | `TEXT` | Optional title |
| `created_at` | `TEXT NOT NULL` | ISO-8601 timestamp |
| `updated_at` | `TEXT` | Last mutation |
| `file_path` | `TEXT` | Relative `.md` path in `MEMORIES_DIR` |
| `access_count` | `INTEGER NOT NULL DEFAULT 0` | Read frequency |
| `last_accessed_at` | `TEXT` | Last read timestamp |
| `salience` | `REAL NOT NULL DEFAULT 0.5` | Computed retention score (0–1) |
| `pinned` | `INTEGER NOT NULL DEFAULT 0` | Exempt from decay if `1` |
| `deleted_at` | `TEXT` | Soft-delete timestamp |
| `grace_until` | `TEXT` | Grace period before hard delete |
| `superseded_by` | `TEXT` | ID of newer memory that replaces this one |

**Indexes:** `idx_memories_scope`, `_project_id`, `_project_path`, `_context`, `_session`, `_created`, `_type`, `_superseded`, `_fts_rowid`.

**FTS5:** `memories_fts` virtual table indexed on `title`, `content`, `tags`. Triggers keep `memories_fts` in sync on insert/update/delete. `fts_rowid` is a dedicated, stable column so re-ingesting conversations does not shift FTS5 rowids.

### `observations` — agent activity log

Captures tool use and session events via the hook router. Not curated; used for audit and observability.

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | UUID |
| `session_id` | `TEXT NOT NULL` | Agent session |
| `kind` | `TEXT NOT NULL` | e.g. `tool_use`, `session_end` |
| `agent` | `TEXT` | Agent name |
| `cwd` | `TEXT` | Working directory |
| `project_id` | `TEXT` | Resolved project |
| `title` | `TEXT` | Event title |
| `body` | `TEXT` | Event body |
| `created_at` | `TEXT NOT NULL` | ISO timestamp |

**Indexes:** `idx_obs_session`, `idx_obs_kind`, `idx_obs_created`.

### `handoffs` — cross-agent handoffs

Represents a "where we left off" package that can be accepted by another agent.

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | UUID |
| `session_id` | `TEXT NOT NULL` | Originating session |
| `from_agent` | `TEXT NOT NULL` | Source agent |
| `project_id` | `TEXT` | Target project |
| `project_path` | `TEXT` | Absolute path |
| `context` | `TEXT` | Branch |
| `status` | `TEXT NOT NULL DEFAULT 'open'` | `open`, `accepted`, `closed` |
| `summary` | `TEXT NOT NULL` | Handoff summary |
| `open_questions` | `TEXT` | Unresolved questions |
| `next_steps` | `TEXT` | Suggested next actions |
| `accepted_by` | `TEXT` | Agent that accepted |
| `accepted_at` | `TEXT` | Acceptance timestamp |
| `created_at` | `TEXT NOT NULL` | ISO timestamp |
| `expires_at` | `TEXT` | Expiration timestamp |

**Indexes:** `idx_handoffs_status`, `idx_handoffs_project`, `idx_handoffs_expires`.

### `audit_log` — all mutations

Every create, update, delete, pin, handoff, and session-end is logged here.

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | UUID |
| `action` | `TEXT NOT NULL` | e.g. `create_memory`, `delete_memory`, `end_session` |
| `target_type` | `TEXT NOT NULL` | `memory`, `session`, `handoff` |
| `target_id` | `TEXT NOT NULL` | Row UUID |
| `agent` | `TEXT` | Agent name |
| `details` | `TEXT` | Short summary |
| `created_at` | `TEXT NOT NULL` | ISO timestamp |

**Indexes:** `idx_audit_action`, `idx_audit_target`, `idx_audit_created`.

### `schema_meta` — version tracking

Stores `version` and other metadata for migration detection.

## sqlite-vec vector store

Conversation search maintains a separate SQLite file (default `data/conversations/.vec.db`) with a `vec0` virtual table:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories
USING vec0(embedding float[<dim>])
```

A `metadata` table maps `rowid` → `path`, `title`, `source`. Embeddings are produced by the encoder selected in `MemoryConfig.vector_encoder_model` (`spacy` or `nomic`).

## Retention tiers and salience

`src/mem0ry/db/retention.py` implements a tiered decay model:

| `memory_type` | Tier | Max lifetime | Default pinned |
|---|---|---|---|
| `log` | working | 90 days | no |
| `pattern` | procedural | 365 days | no |
| `fact` | semantic | ~100 years | yes |
| `decision` | semantic | ~100 years | yes |

**Salience formula** (`compute_salience`):
- Base = `0.5` for `log`/`pattern`, `0.9` for `fact`/`decision`.
- Time decay: `exp(-lambda × days_old)` with `lambda = 0.005`.
- Access boost: Gaussian around `mu = 0.01`, `sigma = 0.3`.
- Result clamped to `[0, 1]`.

**Forget sweep** (`forget_sweep` in `retention.py`):
1. Soft-delete memories whose `salience < threshold` and `grace_until` has passed.
2. Hard-delete memories whose `deleted_at` + retention tier max days has passed.
3. Pinned memories are exempt from both steps.

Run via CLI: `mymem0ry forget-sweep [--dry-run]`.

## Migration history

`src/mem0ry/db/migrate.py` handles upgrades from older schema versions. Key recent migrations:

- **v8 → v9** — added `fts_rowid INTEGER UNIQUE`, `project_id`, `project_path`, `context`, `session_id`, `memory_type`, `source`, `tags`, `access_count`, `last_accessed_at`, `salience`, `pinned`, `deleted_at`, `grace_until`, `superseded_by`.

When changing schema-related code, always bump `_SCHEMA_VERSION` in `schema.py` and add a migration step in `migrate.py`.
