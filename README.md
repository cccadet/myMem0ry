# myMem0ry

Personal memory system using **KV Cache** — no fine-tuning, no vector store, no latency.

## How it works

```
[Setup — runs once per memory update]
Conversations → Ollama extracts memories → memories.txt
memories.txt → transformers builds KV cache → memoria.kvcache (~50-200 MB)

[Chat — runs every time]
memoria.kvcache (instant load) + question → answer
```

The model has already "read" your memories before you ask anything.
The KV cache is the internal attention state after processing the memory text —
not an index, not an embedding, it's the model's own internal representation.

## Architecture

1. **Parser** — `src/mem0ry/parsers/openai.py` walks the OpenAI `mapping` tree, filters `user`/`assistant` turns.
2. **Memory extraction** — `src/mem0ry/kvcache/extract.py` sends each conversation to Ollama and extracts factual memories.
3. **KV cache build** — `src/mem0ry/kvcache/model.py` processes the memories through the model and saves the KV cache.
4. **Chat** — `src/mem0ry/kvcache/model.py` loads the cache and generates responses.
5. **Search** — `src/mem0ry/conversations/search*.py` provides multiple search backends (ripgrep, BM25, FTS5).
6. **Ask** — `src/mem0ry/conversations/ask.py` searches conversations and generates answers on-the-fly.

## Setup

```bash
# Install dependencies
uv sync

# Install model in Ollama
ollama pull unsloth/Qwen3.5-0.8B
```

## Commands

### Memory pipeline (pre-built KV cache)

```bash
# 1. Parse conversations and extract memories via Ollama
mymem0ry build --source data/openai/export --output data/memories

# 2. Build KV cache from memories (run once, or when memories change)
mymem0ry build-cache --memories data/memories/memories.txt

# 3. Chat with your memories
mymem0ry chat "Qual é o meu nome?"
mymem0ry chat "O que eu estava estudando?"

# Interactive mode
mymem0ry interactive
```

### Conversation pipeline (search + inference)

```bash
# 1. Split OpenAI export into .md files organized by date
mymem0ry split

# 2. Search conversations (no model inference)
mymem0ry search "qdrant"                        # ripgrep (default)
mymem0ry search "qdrant" --backend bm25         # BM25
mymem0ry search "qdrant" --backend fts5         # SQLite FTS5

# 3. Ask a question (search + model inference)
mymem0ry ask "o que eu falei sobre qdrant?"
mymem0ry ask "qdrant" --backend bm25

# Interactive ask (model stays loaded)
mymem0ry ask -i "qdrant"
```

### Search backends

| Backend | Description | Index |
|---------|-------------|-------|
| `ripgrep` | Regex keyword search via ripgrep (default) | None — searches files directly |
| `bm25` | TF-IDF ranking with BM25Okapi | `data/conversations/.bm25_index.pkl` |
| `fts5` | SQLite full-text search | `data/conversations/.fts5_index.db` |

```bash
# Build search indexes (BM25 and FTS5)
mymem0ry index                # all backends
mymem0ry index --backend bm25 # only BM25
mymem0ry index --backend fts5 # only FTS5
```

### Benchmark

Compare all search backends side by side:

```bash
mymem0ry benchmark "o que eu falei sobre qdrant?"
mymem0ry benchmark "qdrant" --top-k 5
```

Output:

```
Query: o que eu falei sobre qdrant?

Backend      Tempo (ms)   Arquivos  Top match
----------------------------------------------
ripgrep         12.3         3  correcao-codigo-splade-qdrant.md
bm25             5.1         3  correcao-codigo-splade-qdrant.md
fts5             2.8         3  correcao-codigo-splade-qdrant.md
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EXTRACTION_BACKEND` | Backend for memory extraction | `ollama` |
| `OLLAMA_MODEL` | Ollama model for extraction | `qwen3.5:0.8b` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434/v1` |
| `KVCACHE_MODEL` | Model for inference/cache | `Qwen/Qwen3.5-0.8B` |
| `KVCACHE_PATH` | KV cache file path | `memoria.kvcache` |
| `KVCACHE_META_PATH` | Metadata JSON path | `memoria.meta.json` |
| `KVCACHE_MAX_TOKENS` | Max tokens for cache/prompt | `1024` |
| `EXTRACTION_MAX_TOKENS` | Max tokens for extraction | `2048` |
| `EXTRACTION_TEMPERATURE` | Temperature for extraction | `0.3` |
| `CHAT_MAX_NEW_TOKENS` | Max new tokens in chat | `256` |
| `CONVERSATIONS_DIR` | Directory for .md conversations | `data/conversations` |
| `SEARCH_TOP_K` | Number of results to retrieve | `3` |
| `SEARCH_BACKEND` | Default search backend | `ripgrep` |

## Example

```
$ mymem0ry chat "Qual é o nome do meu cachorro?"
Seu cachorro se chama Rex, um golden retriever de 3 anos.

$ mymem0ry ask "Onde eu moro?"
Você mora em São Paulo, no bairro Vila Madalena.
```

## Why KV Cache instead of fine-tuning

Fine-tuning modifies model weights to "memorize" information —
in a small model this causes instability and catastrophic forgetting.

The KV cache doesn't touch the weights. It injects the already-processed
representation of memories directly into the attention layers, as if the model
had just read the text. It's more faithful and more predictable.

## Outputs

- `data/memories/memories.txt` — extracted memories
- `data/conversations/YYYY-MM-DD/*.md` — split conversations
- `data/conversations/.bm25_index.pkl` — BM25 search index
- `data/conversations/.fts5_index.db` — FTS5 search index
- `memoria.kvcache` — serialized KV cache (~50-200 MB)
- `memoria.meta.json` — cache metadata

## Testing & Formatting

```bash
uv run pytest
uv run ruff check .
```
