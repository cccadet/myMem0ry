# AGENTS.md — myMem0ry

Personal memory system with semantic search, scoped storage (session/context/project/global), and MCP server. Python 3.11+, managed with `uv`.

## Setup

```bash
bin/setup                          # Idempotent bootstrap (deps + spaCy model + ripgrep check)
uv sync --group dev                # Dependencies only
uv run spacy download en_core_web_lg   # Required for search, expand, hybrid backends
# For Portuguese: SPACY_MODEL=pt_core_news_lg
```

ripgrep (`rg`) must be on PATH — the default `ripgrep` search backend shells out to it.

## Commands

```bash
# Lint → typecheck → test (CI order, from .github/workflows/ci.yml)
uv run ruff check .
uv run mypy src/mem0ry
uv run pytest                          # coverage gate: fail_under=80 in pyproject.toml

# Single test file or test
uv run pytest tests/test_config.py
uv run pytest tests/test_config.py::test_default_values -k test_default

# CLI entrypoints (from pyproject.toml [project.scripts])
mymem0ry split [source]               # Export → .md by date (auto-detects openai/gemini/claude)
mymem0ry search "query"               # ripgrep default
mymem0ry search "query" --backend hybrid --expand  # BM25+vector RRF fusion + spaCy expansion
mymem0ry index                        # Build BM25 + FTS5 + vector indexes
mymem0ry migrate                      # .md → SQLite structured memories
mymem0ry migrate --reprocess          # Drop DB + reingest into v3 schema
mymem0ry stats                        # DB overview (by scope, type, source, project)
mymem0ry projects                     # List projects with memories (by git remote URL)
mymem0ry doctor                       # System health check (6 checks)
mymem0ry decay [--days 90] [--dry-run]  # Remove old session logs
mymem0ry benchmark "query"            # Compare search backends
mymem0ry expand "token"               # Semantically related tokens
mymem0ry dataset                      # ChatML JSONL (legacy)

# CLI commands used by hooks
mymem0ry context --cwd .              # Load context for current project (session-start)
mymem0ry save "Title" "Content"       # Save a memory (session-end)
mymem0ry log "message"                # Quick session log (lifecycle hooks)

# MCP server
mymem0ry-mcp                          # Starts FastMCP server
```

## Architecture

```
src/mem0ry/
├── config.py                 # MemoryConfig dataclass — loads .env via dotenv
├── mcp_server.py             # FastMCP server — 9 tools, global state (_session_id, _expander)
├── cli/main.py               # Typer app — all CLI commands
├── db/
│   ├── connection.py         # SQLite + sqlite-vec extension
│   ├── schema.py             # init_schema() — memories table v3 (scopes + memory_type + access tracking)
│   ├── store.py              # CRUD: create_memory, get_context, search_memories, decay_memories, ...
│   └── migrate.py            # migrate_v1_to_v2() + migrate_v2_to_v3() — .md → SQLite
├── parsers/                  # Auto-detected by content shape
│   ├── openai.py             # ChatGPT JSON (mapping tree)
│   ├── gemini.py             # Google Takeout JSON (safeHtmlItem)
│   └── claude.py             # ClaudeCodeParser (JSONL) + ClaudeExportParser (JSON)
├── conversations/
│   ├── writer.py             # split_conversations() → .md files
│   ├── search.py             # ripgrep backend
│   ├── search_bm25.py        # BM25Okapi
│   ├── search_fts.py         # SQLite FTS5
│   ├── search_hybrid.py      # RRF fusion: 1/(k + rank) combining BM25 + vector
│   ├── embeddings.py         # SpacyEncoder — nlp(text).vector, 300-dim
│   ├── vector_store.py       # sqlite-vec wrapper
│   └── spacy_expand.py       # SpacyConceptSearch — query expansion
├── dataset/                  # Legacy ChatML fine-tuning pipeline
└── utils/
    ├── filenames.py          # sanitize_title() — shared by writer.py + mcp_server.py
    ├── git_context.py        # resolve_project_id(), resolve_context(), resolve_full_context()
    ├── logging.py            # configure_logging()
    └── paths.py              # ensure_dir()
```

### Key facts

- **Memory scopes**: `global` / `project` / `context` / `session` — validated by `_VALID_SCOPES` in `db/store.py:17`.
- **Memory types**: `fact` / `decision` / `pattern` / `log` — validated by `_VALID_MEMORY_TYPES` in `db/store.py:18`. Used for decay differentiation.
- **Source values**: `claude-code` / `opencode` / `codex` / `manual` / `import` — validated by `_VALID_SOURCES` in `db/store.py:16`.
- **`get_context()`** aggregates session → context → project → global (4-level cascata), returning up to `top_k` results distributed across scopes.
- **Project resolution**: `resolve_project_id()` uses `git remote get-url origin` (raw URL). Falls back to None if not a git repo. See `utils/git_context.py`.
- **Context resolution**: `resolve_context()` uses `git rev-parse --abbrev-ref HEAD`. Generic — can be branch, worktree, feature, etc.
- **Schema version**: v3. `db/schema.py` sets `_SCHEMA_VERSION = 3`.
- **Decay**: `decay_memories()` in `db/store.py` removes session-scoped `log` memories with no access in N days. `touch_memory()` increments `access_count`.
- **Hybrid search** uses Reciprocal Rank Fusion (`RRF_K=60` by default) to merge BM25 and vector rankings.
- **Embeddings** are spaCy doc vectors (300-dim, no external model API). Default model: `en_core_web_lg`.
- **MCP server** uses module-level global state (`_session_id`, `_expander`) with lazy init — not thread-safe.
- **MCP tools** receive `cwd` parameter and resolve project_id + context automatically via `resolve_full_context()`.
- `sanitize_title()` in `utils/filenames.py` is the single source for filename sanitization, shared between `writer.py` and `mcp_server.py`.
- `config.py` loads `.env` from the project root on import (`load_dotenv` at module level).
- `data/` is gitignored. DB files (`data/memories.db`, `data/conversations/.vec.db`) are created at runtime.
- The `system_prompt` field exists on `MemoryConfig` (line 24) and is used by `pipeline/dataset.py` via `getattr`.

## Tests

- No `conftest.py`. Tests import directly from `mem0ry.*`.
- Tests use `pytest.fixture` for temp DBs in `test_db_store.py`.
- Coverage enforced at 80% (`fail_under = 80` in `pyproject.toml`).
- `mutmut` is configured for mutation testing (`uv run mutmut run`).

## Code style

- Functions: 4–20 lines. Files: under 500 lines.
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
- Types: explicit. No `Any`, no untyped functions.
- Max 2 levels of indentation. Early returns over nesting.
- Exception messages include the offending value and expected shape.
- Preserve existing comments on refactor — they carry intent.
- Docstrings: WHY + one usage example on public functions.
- Format/lint with `ruff` only. No style discussion beyond that.
- Structured JSON for debug logging, plain text for CLI output.
