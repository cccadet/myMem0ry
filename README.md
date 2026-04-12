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

## Setup

```bash
# Install dependencies
uv sync

# Install model in Ollama
ollama pull unsloth/Qwen3.5-0.8B
```

## Commands

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

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MEMORY_MODEL` | Model for extraction + KV cache | `unsloth/Qwen3.5-0.8B` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434/v1` |
| `KVCACHE_PATH` | KV cache file path | `memoria.kvcache` |
| `KVCACHE_META_PATH` | Metadata JSON path | `memoria.meta.json` |
| `KVCACHE_MAX_TOKENS` | Max tokens for memories | `1024` |
| `EXTRACTION_MAX_TOKENS` | Max tokens for extraction | `2048` |
| `EXTRACTION_TEMPERATURE` | Temperature for extraction | `0.3` |
| `CHAT_MAX_NEW_TOKENS` | Max new tokens in chat | `256` |

## Example

```
$ mymem0ry chat "Qual é o nome do meu cachorro?"
Seu cachorro se chama Rex, um golden retriever de 3 anos.

$ mymem0ry chat "Onde eu moro?"
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
- `memoria.kvcache` — serialized KV cache (~50-200 MB)
- `memoria.meta.json` — cache metadata

## Testing & Formatting

```bash
uv run pytest
uv run ruff check .
```
