# myMem0ry

Personal memory search system with semantic query expansion.

Searches through your ChatGPT and Gemini conversations using multiple backends (ripgrep, BM25, FTS5), with optional semantic query expansion using spaCy word vectors.

## Setup

```bash
uv sync
uv run spacy download pt_core_news_lg   # download word vectors (run once)
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
mymem0ry search "qdrant" --expand     # expands query with spaCy similar tokens

# Show semantically related tokens
mymem0ry expand "france"              # top-10 related tokens
mymem0ry expand "france" -k 20        # more results

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

The `--expand` flag uses spaCy word vectors (`pt_core_news_lg`) to find semantically related words. It operates at the word level — no BPE/subword fragmentation.

```
$ mymem0ry expand "france"
Query: france

Token                             Score
----------------------------------------
paris                              0.63
french                             0.61
...
```

### MCP Server

myMem0ry also runs as an MCP server with tools for saving and searching memories:

```bash
mymem0ry-mcp    # starts the MCP server
```

Tools: `log_message`, `save_memory`, `save_conversation`, `search_memory`, `read_memory`.

### Supported sources

| Source | Directory | Format |
|--------|-----------|--------|
| OpenAI (ChatGPT) | `data/openai/export/` | JSON with `mapping` tree |
| Gemini (Google Takeout) | `data/gemini/` | `Minhaatividade.json` |

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
| `EXPAND_TOP_K` | `10` | Number of similar tokens to generate |
| `CONVERSATIONS_DIR` | `data/conversations` | Directory with .md conversations |
| `SEARCH_TOP_K` | `3` | Number of results to retrieve |
| `SEARCH_BACKEND` | `ripgrep` | Default search backend: ripgrep, bm25, fts5 |
| `SPACY_MODEL` | `pt_core_news_lg` | spaCy model for query expansion |

## Testing & Linting

```bash
uv run pytest
uv run ruff check .
uv run mypy src/mem0ry
```
