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
mymem0ry warmup                       # pre-cache FFN walk weights (run once)
mymem0ry search "qdrant" --expand     # expands query with similar tokens

# Show semantically related tokens
mymem0ry expand "france"              # top-10 related tokens
mymem0ry expand "france" -k 20 -g 256 # more results, more features

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

The `--expand` flag uses FFN walk (LARQL-inspired) to find semantically related concepts. Instead of surface-level embedding similarity, it computes GeGLU activations (`silu(gate) * up`) on the model's FFN layers to access the semantic knowledge stored in the weights.

```
$ mymem0ry expand "france"
Query: france

Token                             Score  Layer
--------------------------------------------------
paris                              0.63    L16
french                             0.61    L16
usa                                0.60    L22
parisian                           0.58    L16
america                            0.53    L22
```

Run `mymem0ry warmup` once to build the FFN cache. You can control which layers are cached with `--layers`:

```bash
mymem0ry warmup -l 14-27            # knowledge band (recommended for Gemma 3 4B)
```

Middle layers hold semantic knowledge (concept relations). Final layers are in token-prediction mode and produce poor results. The knowledge band follows the LARQL segmentation: syntax → **knowledge** → output.

| Model | Total layers | Knowledge band | hidden | intermediate | Cache size |
|-------|-------------|----------------|--------|-------------|------------|
| google/gemma-3-4b-it | 34 | L14-L27 | 2560 | 10240 | ~1.7 GB |
| google/gemma-4-E4B | 42 | L18-L32 | 2560 | 10240 | ~1.7 GB |
| Qwen/Qwen3.5-0.8B | 24 | L10-L18 | 896 | 4864 | ~80 MB |

The expand command supports tuning:

```bash
mymem0ry expand "france" -k 20       # more results
mymem0ry expand "france" -g 256      # more features per layer (default: 32)
mymem0ry expand "france" --debug     # show gate scores and feature details
```

If no FFN cache exists, falls back to embedding cosine similarity.

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
| `SEARCH_BACKEND` | `ripgrep` | Default search backend: ripgrep, bm25, fts5 |

## Testing & Linting

```bash
uv run pytest
uv run ruff check .
```
