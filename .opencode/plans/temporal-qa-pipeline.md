# Temporal Q&A Pipeline Implementation Plan

## Summary

Add temporal awareness and synthetic Q&A generation to the myMem0ry pipeline so the fine-tuned model learns **when** conversations happened and can answer temporal queries about the user's history.

## Decisions Made

- **Q&A Generation API**: z.ai (GLM-4.7-FlashX, $0.07/M input, $0.40/M output)
- **Date format**: Dynamic system prompt (not message prefixes)
- **Q&A per conversation**: 3-5 pairs
- **Incremental processing**: Cache Q&A results, only call API for new/changed conversations

## API Details

- **Endpoint**: `https://api.z.ai/api/paas/v4/`
- **SDK**: OpenAI Python SDK (compatible)
- **Model**: `glm-4.7-flashx`
- **Docs**: https://docs.z.ai/guides/llm/glm-5.1

## Files to Change

### 1. `pyproject.toml` — Add openai dependency

Add `"openai>=1.0"` to the dependencies list.

### 2. `.env` — Add z.ai config

```
ZAI_API_KEY=your-key-here
ZAI_BASE_URL=https://api.z.ai/api/paas/v4/
QA_GENERATION_MODEL=glm-4.7-flashx
```

### 3. NEW: `src/mem0ry/dataset/temporal.py`

Functions:
- `format_timestamp(ts: str | None) -> str | None` — Convert raw timestamps to human-readable dates
- `build_temporal_system_prompt(conversation: ParsedConversation, base_prompt: str) -> str` — Build system prompt with conversation date context
- `enrich_conversations(conversations: Sequence[ParsedConversation]) -> list[ParsedConversation]` — Sort chronologically and ensure timestamps are available

### 4. NEW: `src/mem0ry/dataset/qa_cache.py`

Functions:
- `QACacheEntry` dataclass: `conversation_id, content_hash, qa_pairs, generated_at, model`
- `QACache` class: manages loading/saving the cache JSONL file
  - `load(path) -> dict[str, QACacheEntry]`
  - `save(path, entries)`
  - `compute_hash(messages) -> str`
  - `is_cached(conversation_id, content_hash) -> bool`
  - `get(conversation_id) -> QACacheEntry | None`
  - `add(entry: QACacheEntry)`

### 5. NEW: `src/mem0ry/dataset/qa_generator.py`

Functions:
- `QAPair` dataclass: `question, answer`
- `generate_qa_pairs(conversation: ParsedConversation, *, client, model, n_pairs) -> list[QAPair]` — Call z.ai API to generate Q&A
- `_build_qa_prompt(conversation: ParsedConversation, n_pairs: int) -> str` — Build the prompt for the LLM
- `_parse_qa_response(response_text: str) -> list[QAPair]` — Parse JSON response

### 6. MODIFY: `src/mem0ry/dataset/builder.py`

- `_build_messages()` should accept a `ParsedConversation` and inject temporal context into system prompt
- `build_chatml_examples()` should use `build_temporal_system_prompt()` from temporal.py

### 7. MODIFY: `src/mem0ry/training/config.py`

Add to TrainingConfig:
- `zai_api_key: str | None = None`
- `zai_base_url: str = "https://api.z.ai/api/paas/v4/"`
- `qa_generation_model: str = "glm-4.7-flashx"`
- `qa_pairs_per_conversation: int = 4`
- `qa_cache_path: str = "data/qa_cache.jsonl"`
- `enable_qa_generation: bool = True`

### 8. MODIFY: `src/mem0ry/pipeline/dataset.py`

Major changes:
- Import temporal enrichment and Q&A generator
- After parsing, enrich conversations with temporal context
- For each conversation, check cache → generate Q&A if needed
- Merge ChatML chunks + Q&A pairs into final dataset
- New function signature with additional parameters

### 9. MODIFY: `scripts/build_dataset.py`

Add CLI parameters:
- `--force-qa: bool = False` — Regenerate all Q&A
- `--regen-qa: list[str] | None = None` — Regenerate specific conversation IDs
- `--qa-model: str = "glm-4.7-flashx"` — Override Q&A model
- `--no-qa: bool = False` — Skip Q&A generation entirely

## Implementation Order

1. pyproject.toml (add openai dep)
2. .env (add z.ai config)
3. temporal.py (create)
4. qa_cache.py (create)
5. qa_generator.py (create)
6. config.py (modify)
7. builder.py (modify)
8. dataset __init__.py (update exports)
9. pipeline/dataset.py (modify)
10. scripts/build_dataset.py (modify)
11. Run `uv sync` and `uv run ruff check .`
