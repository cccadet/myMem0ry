# myMem0ry

Fine-tune `unsloth/Qwen3-0.6B-unsloth-bnb-4bit` with LoRA adapters so your exported conversations become a personal memory model.

## Architecture

1. **Parser & extractor** – `src/mem0ry/parsers/openai.py` walks the OpenAI `mapping` tree, filters `user`/`assistant` turns, and normalizes multi-part messages into `ParsedConversation` objects.
2. **ChatML builder** – `src/mem0ry/dataset` handles chunking, quality filtering, deduplication, and statistics before producing `train.jsonl` / `val.jsonl` outputs.
3. **LoRA training** – `src/mem0ry/training/train.py` wires `FastLanguageModel`, `SFTTrainer`, and the dataset to run the fine-tuning job.
4. **Export** – `src/mem0ry/training/export.py` emits a GGUF bundle compatible with Ollama and `llama.cpp`.

Supporting helpers live under `src/mem0ry/utils` and the CLI entry point is `src/mem0ry/cli/main.py`.

## Setup

```bash
# Initialize the uv project & install dependencies
uv init --name myMem0ry --package
uv add unsloth unsloth_zoo torch transformers trl peft datasets typer pydantic
uv add --dev pytest ruff
```

## Commands

```bash
py scripts/build_dataset.py --source data/openai/export --output data/processed
py scripts/train.py --dataset data/processed/train.jsonl --output output/memory_model
py scripts/export.py --model output/memory_model/memory_model_lora --output output/memory_model --quantization q4_k_m
```

Typer-powered CLI (installed as `mymem0ry`) mirrors the same functionality plus `stats` and `pipeline` shortcuts:

```
mymem0ry build --source data/openai/export --output data/processed
mymem0ry stats --target data/processed
mymem0ry train --dataset data/processed/train.jsonl --output output/memory_model
mymem0ry export --model output/memory_model/memory_model_lora --output output/memory_model
mymem0ry pipeline --source data/openai/export --processed data/processed --model-output output/memory_model
```

## Outputs

- `data/processed/train.jsonl`, `data/processed/val.jsonl`, `data/processed/stats.json`
- `output/memory_model/memory_model_lora` (LoRA weights)
- `output/memory_model/unsloth.Q4_K_M.gguf` (GGUF export)

## Testing & Formatting

```bash
uv run pytest
uv run ruff check .
```
