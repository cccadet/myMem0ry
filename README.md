# myMem0ry

Personal memory search system with semantic query expansion.

Searches through your ChatGPT and Gemini conversations using multiple backends (ripgrep, BM25, FTS5), with optional semantic query expansion that finds related terms using a language model's embedding space.

## Setup

```bash
uv sync
```

## Usage

```bash
# Split conversations into .md files organized by date
mymem0ry split                        # auto-detects OpenAI and/or Gemini exports

# Search conversations
mymem0ry search "qdrant"              # ripgrep (default)
mymem0ry search "qdrant" --backend bm25
mymem0ry search "qdrant" --backend fts5

# Search with semantic query expansion
mymem0ry warmup                       # pre-cache embeddings (run once)
mymem0ry search "qdrant" --expand     # expands query with similar tokens

# Compare backends side by side
mymem0ry benchmark "python"
mymem0ry benchmark "python" --expand

# Build search indexes
mymem0ry index                        # all backends
mymem0ry index --backend bm25
mymem0ry index --backend fts5
```

## How it works

### Conversation pipeline

1. **Split** — Parses exports (OpenAI JSON or Gemini Takeout JSON) and writes each conversation as a `.md` file organized by date in `data/conversations/YYYY-MM-DD/`.
2. **Search** — Searches across all `.md` files using ripgrep, BM25, or SQLite FTS5.

### Query expansion

The `--expand` flag uses a model's embedding matrix to find semantically similar tokens. The query is expanded with those tokens before being passed to the search backend.

On first use (or after `mymem0ry warmup`), the embedding matrix and tokenizer are cached to `data/.cache/embeddings/`. Subsequent runs load the cache directly instead of the full model (~3s vs ~7s).

### Supported sources

| Source | Directory | Format |
|--------|-----------|--------|
| OpenAI (ChatGPT) | `data/openai/export/` | JSON with `mapping` tree |
| Gemini (Google Takeout) | `data/Gemini/` | `Minhaatividade.json` |

Auto-detected on `mymem0ry split` — both sources write to the same `data/conversations/` output.

## Search backends

| Backend | Description | Index |
|---------|-------------|-------|
| `ripgrep` | Regex keyword search (default) | None |
| `bm25` | TF-IDF ranking with BM25Okapi | `.bm25_index.pkl` |
| `fts5` | SQLite full-text search | `.fts5_index.db` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `Qwen/Qwen3.5-0.8B` | Model for query expansion |
| `EXPAND_TOP_K` | `10` | Number of similar tokens to generate |
| `CONVERSATIONS_DIR` | `data/conversations` | Directory with .md conversations |
| `SEARCH_TOP_K` | `3` | Number of results to retrieve |
| `SEARCH_BACKEND` | `ripgrep` | Default search backend |

## Testing & Linting

```bash
uv run pytest
uv run ruff check .
```
