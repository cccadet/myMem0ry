# myMem0ry

> Personal memory for AI agents. Zero API keys. Offline. Pure Python.

[![CI](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml/badge.svg)](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml)

## What it does

- Ingests conversations from ChatGPT, Gemini, Claude → indexed `.md` files
- Semantic search (spaCy + sqlite-vec + BM25/FTS5/hybrid)
- MCP server with scoped memory (global/project/session)
- Works with Claude Code, OpenCode, Cursor

## Quick start

```bash
uvx mymem0ry split data/openai/export
uvx mymem0ry search "python decorators"
uvx mymem0ry search "auth" --backend hybrid --expand
```

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
  Agents (Claude Code, OpenCode, Cursor...)
```

## Memory scopes

| Scope | What it stores | `save_memory` args |
|---|---|---|
| `global` | Preferences, stack, patterns | `scope="global"` |
| `project` | Technical decisions, bugs, context | `scope="project", project_path="/abs/path"` |
| `session` | Current session summary | `scope="session", session_id="abc123"` |

`get_context()` aggregates all 3 levels — session > project > global.

## MCP Tools

| Tool | Description |
|---|---|
| `log_message` | Log a message in the current session |
| `save_memory` | Save a memory with scope |
| `save_conversation` | Save a full conversation |
| `read_memory` | Read a memory file's content |
| `search_memory` | Search with semantic query expansion |
| `get_context` | Aggregate context from all scopes |
| `list_scopes` | List scopes with memory counts |
| `end_session` | Mark session as completed |
| `memory_stats` | Database statistics |

## CLI commands

```bash
mymem0ry split                        # Export → .md by date
mymem0ry search "query"               # Search (ripgrep default)
mymem0ry search "query" --backend hybrid --expand
mymem0ry benchmark "python"           # Compare backends
mymem0ry expand "france"              # Semantically related tokens
mymem0ry index                        # Build BM25 + FTS5 + vector indexes
mymem0ry migrate                      # Migrate .md → SQLite memories
mymem0ry stats                        # Memory database overview
mymem0ry projects                     # List projects with memories
mymem0ry doctor                       # System health check
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `EXPAND_TOP_K` | `10` | Similar tokens in expansion |
| `CONVERSATIONS_DIR` | `data/conversations` | Directory with .md conversations |
| `SEARCH_TOP_K` | `3` | Number of search results |
| `SEARCH_BACKEND` | `ripgrep` | Default backend: ripgrep, bm25, fts5, hybrid |
| `SPACY_MODEL` | `pt_core_news_lg` | spaCy model for query expansion |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | sqlite-vec database path |
| `EMBEDDING_DIM` | `300` | Embedding dimensionality |
| `RRF_K` | `60` | RRF constant for hybrid search |
| `DB_PATH` | `data/memories.db` | SQLite memories database path |

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
