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

# Build normal (incremental - só processa conversas novas)
mymem0ry build --source data/openai/export --output data/processed
# Forçar regeneração de todo Q&A
mymem0ry build --source data/openai/export --output data/processed --force-qa
# Regenerar Q&A de conversas específicas
mymem0ry build --source data/openai/export --output data/processed --regen-qa abc-123 def-456
# Build sem Q&A (só chunks de conversa com datas)
mymem0ry build --source data/openai/export --output data/processed --no-qa
# Extrair Q&A diretamente dos turnos da conversa (sem modelo)
mymem0ry build --source data/openai/export --output data/processed --qa-backend turns

Typer-powered CLI (installed as `mymem0ry`) mirrors the same functionality plus `stats` and `pipeline` shortcuts:

```
mymem0ry build --source data/openai/export --output data/processed
mymem0ry stats --target data/processed
mymem0ry train --dataset data/processed/train.jsonl --output output/memory_model
mymem0ry export --model output/memory_model/memory_model_lora --output output/memory_model
mymem0ry quantize output/memory_model/unsloth.F16.gguf --method q4_k_m
mymem0ry pipeline --source data/openai/export --processed data/processed --model-output output/memory_model
```

### QA Backends (`--qa-backend`)

The `build` command supports multiple backends for generating Q&A training examples:

| Backend | Description | Requirements |
|---------|-------------|--------------|
| `turns` | Extrai pares pergunta/resposta diretamente dos turnos `user` → `assistant` das conversas. Sem chamadas de API, sem custo, instantâneo. | Nenhum |
| `api` | Gera Q&A sintético usando a API Z AI (padrão). | `ZAI_API_KEY` no `.env` |
| `ollama` | Gera Q&A sintético via servidor Ollama local. | Ollama rodando localmente com modelo instalado |
| `llamacpp` | Gera Q&A sintético via llama.cpp direto (GPU/CPU). | `--llamacpp-model` ou `LLAMACPP_MODEL_PATH` |

Exemplos:

```bash
# Turns (sem modelo, extrai dos turnos)
mymem0ry build --qa-backend turns --source data/openai/export --output data/processed

# API Z AI (padrão)
mymem0ry build --qa-backend api --qa-model glm-4.7-flashx --source data/openai/export --output data/processed

# Ollama local
mymem0ry build --qa-backend ollama --ollama-model qwen3:0.6b --source data/openai/export --output data/processed

# llama.cpp direto
mymem0ry build --qa-backend llamacpp --llamacpp-model models/qwen3-0.6b.gguf --source data/openai/export --output data/processed
```

### Outras opções do build

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--max-seq-length` | Comprimento máximo de sequência por chunk | `2048` |
| `--overlap-turns` | Turnos de sobreposição entre chunks | `2` |
| `--min-turns` | Mínimo de turnos para manter um exemplo | `2` |
| `--val-ratio` | Proporção do conjunto de validação | `0.05` |
| `--qa-pairs` | Pares Q&A por conversa (backends api/ollama/llamacpp) | `4` |
| `--qa-cache` | Caminho do cache Q&A (JSONL) | `data/qa_cache.jsonl` |
| `--force-qa` | Força regeneração de todo o cache Q&A | `false` |
| `--regen-qa` | Regenera Q&A apenas para IDs específicos | — |
| `--no-qa` | Desabilita geração de Q&A (só chunks) | `false` |
| `--no-temporal` | Desabilita enriquecimento temporal nos prompts | `false` |

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
