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
mymem0ry build --source data/openai/export --output data/processed
mymem0ry train --dataset data/processed/train.jsonl --output output/memory_model
mymem0ry export --model output/memory_model/memory_model_lora --output output/memory_model
ollama create qwen3-memory -f output/memory_model_gguf/Modelfile
mymem0ry quantize output/memory_model/unsloth.F16.gguf --method q4_k_m
```

Typer-powered CLI (installed as `mymem0ry`) mirrors the same functionality plus `stats` and `pipeline` shortcuts:

```
mymem0ry build --source data/openai/export --output data/processed
mymem0ry stats --target data/processed
mymem0ry train --dataset data/processed/train.jsonl --output output/memory_model
mymem0ry export --model output/memory_model/memory_model_lora --output output/memory_model
mymem0ry quantize output/memory_model/unsloth.F16.gguf --method q4_k_m
mymem0ry pipeline --source data/openai/export --processed data/processed --model-output output/memory_model
```

The `export` command now defaults to **F16** (no quantization loss). Add `--quantization q4_k_m` if you want to quantize during export.

## Ollama deployment

### Test with F16 (recommended first step)

`mymem0ry export` produces an F16 GGUF by default, preserving full model quality. After exporting, rebuild the Ollama model:

```bash
ollama build -f output/memory_model_gguf/Modelfile qwen3-0.6-memory output/memory_model_gguf
```

Then test it:

```bash
ollama run qwen3-0.6-memory:latest
```

### Optional: Quantize for production

If you're happy with the model and want a smaller, faster version, quantize the F16 GGUF:

```bash
mymem0ry quantize output/memory_model/unsloth.F16.gguf --method q4_k_m
```

Then rebuild the Ollama model with the quantized GGUF:

```bash
ollama build -f output/memory_model_gguf/Modelfile qwen3-0.6-memory output/memory_model_gguf
ollama run qwen3-0.6-memory:latest
```

The export command also supports `--quantization q4_k_m` to skip the F16 step entirely, and `--no-patch-modelfile` if you need to skip the Modelfile rewrite.

## Outputs

- `data/processed/train.jsonl`, `data/processed/val.jsonl`, `data/processed/stats.json`
- `output/memory_model/memory_model_lora` (LoRA weights)
- `output/memory_model/unsloth.F16.gguf` (GGUF export, default)
- `output/memory_model/unsloth.Q4_K_M.gguf` (if quantized via `--quantization` or `mymem0ry quantize`)

## Testing & Formatting

```bash
uv run pytest
uv run ruff check .
```
