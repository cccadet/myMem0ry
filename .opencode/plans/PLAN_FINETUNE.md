# myMem0ry - Fine-tuning Qwen3-0.6B with LoRA via Unsloth

## Objective

Transform your OpenAI conversation exports into a fine-tuning dataset and train Qwen3-0.6B using LoRA (via Unsloth) so the model internalizes your memories, preferences, and knowledge — turning it into a personal memory model rather than a generic LLM.

---

## Architecture Overview

```
OpenAI Exports (JSON)
    ↓
[1] Parser & Extractor
    ↓
[2] Dataset Builder (ChatML Format)
    ↓
[3] Quality Filter & Deduplication
    ↓
[4] Unsloth LoRA Fine-tuning (Qwen3-0.6B)
    ↓
[5] Export → GGUF (Ollama / llama.cpp compatible)
    ↓
Personal Memory Model
```

---

## Phase 1 — Parse OpenAI Exports

### Input Format
OpenAI exports are JSON files with this structure:
- `conversations-XXX.json` — array of conversations with `mapping` tree
- Each conversation has:
  - `id`, `title`, `create_time`
  - `mapping` — tree of messages with parent/children relationships
  - Each node has `message.author.role` (user/assistant/system)
  - Each node has `message.content.parts` (array of text content)

### Implementation
```
src/mem0ry/parsers/
├── openai.py          # Parse OpenAI export JSON
└── base.py            # Abstract parser interface
```

**Key logic:**
1. Walk the `mapping` tree from root to leaves
2. Extract only `user` and `assistant` messages (skip `system`)
3. Reconstruct chronological order from tree structure
4. Handle multi-part messages (join `content.parts`)
5. Filter empty messages

---

## Phase 2 — Build Fine-tuning Dataset

### Target Format: ChatML (OpenAI style)
```json
{
  "messages": [
    {"role": "user", "content": "What did I tell you about my project last week?"},
    {"role": "assistant", "content": "You mentioned you were working on..."}
  ]
}
```

### Implementation
```
src/mem0ry/dataset/
├── builder.py         # Convert parsed conversations to ChatML
├── splitter.py        # Train/val split
└── stats.py           # Dataset statistics
```

**Key logic:**
1. Each conversation → one ChatML example
2. Split long conversations into chunks (respecting `max_seq_length`)
3. Add system prompt with memory context (optional)
4. Generate dataset statistics (count, avg length, etc.)
5. Save as JSONL file

### Chunking Strategy
For conversations exceeding `max_seq_length`:
- Split at natural conversation boundaries
- Overlap last N messages for context continuity
- Minimum 2 turns per chunk

---

## Phase 3 — Quality Filter & Deduplication

### Implementation
```
src/mem0ry/dataset/
├── filter.py          # Quality filters
└── dedupe.py          # Deduplication
```

**Filters:**
- Remove conversations with only 1 turn
- Remove empty or near-empty messages
- Remove conversations with only system messages
- Filter by minimum quality score (optional)

**Deduplication:**
- Hash-based deduplication on message content
- Remove near-duplicate conversations

---

## Phase 4 — Unsloth LoRA Fine-tuning

### Model: `unsloth/Qwen3-0.6B-unsloth-bnb-4bit`

### Training Script
```
src/mem0ry/training/
├── train.py           # Main training script
├── config.py          # Training configuration
└── export.py          # Export to GGUF
```

### Training Configuration (starting point)
```python
{
    "model_name": "unsloth/Qwen3-0.6B-unsloth-bnb-4bit",
    "max_seq_length": 2048,
    "load_in_4bit": True,
    "lora_r": 32,
    "lora_alpha": 32,
    "lora_dropout": 0.0,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                       "gate_proj", "up_proj", "down_proj"],
    "batch_size": 2,
    "gradient_accumulation_steps": 4,
    "warmup_steps": 5,
    "max_steps": -1,
    "num_train_epochs": 3,
    "learning_rate": 2e-4,
    "weight_decay": 0.01,
    "fp16": True,
    "optim": "adamw_8bit",
    "lr_scheduler_type": "cosine",
    "seed": 42,
}
```

### Training Flow
```python
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from trl import SFTTrainer
from transformers import TrainingArguments

# 1. Load model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3-0.6B-unsloth-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,
)

# 2. Apply chat template
tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

# 3. Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# 4. Load and format dataset
dataset = load_dataset("json", data_files="dataset/train.jsonl", split="train")
dataset = dataset.map(formatting_func, batched=True)

# 5. Train
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=TrainingArguments(...),
)
trainer.train()

# 6. Save
model.save_pretrained("output/memory_model_lora")
tokenizer.save_pretrained("output/memory_model_lora")
```

---

## Phase 5 — Export & Deployment

### Export to GGUF (for Ollama / llama.cpp)
```python
model.save_pretrained_gguf(
    "output/memory_model",
    tokenizer,
    quantization_method="q4_k_m",
)
```

### Ollama Integration
Create a `Modelfile`:
```
FROM ./output/memory_model/unsloth.Q4_K_M.gguf
SYSTEM "You are a personal memory assistant. You know the user's conversations, preferences, and history."
```

Build and run:
```bash
ollama create mymemory -f Modelfile
ollama run mymemory
```

---

## Project Structure

```
myMem0ry/
├── pyproject.toml
├── .env
├── README.md
│
├── src/mem0ry/
│   ├── __init__.py
│   ├── cli/
│   │   └── main.py              # CLI entry point (typer)
│   ├── parsers/
│   │   ├── base.py
│   │   └── openai.py
│   ├── dataset/
│   │   ├── builder.py
│   │   ├── splitter.py
│   │   ├── filter.py
│   │   ├── dedupe.py
│   │   └── stats.py
│   ├── training/
│   │   ├── train.py
│   │   ├── config.py
│   │   └── export.py
│   └── utils/
│       ├── logging.py
│       └── paths.py
│
├── data/
│   ├── openai/export/           # Raw OpenAI exports
│   └── processed/               # Processed datasets
│       ├── train.jsonl
│       ├── val.jsonl
│       └── stats.json
│
├── output/                      # Training outputs
│   └── memory_model/
│
└── scripts/
    ├── build_dataset.py         # CLI: parse → build → filter
    └── train.py                 # CLI: train model
```

---

## CLI Commands

```bash
# Build dataset from OpenAI exports
myMem0ry build --source data/openai/export --output data/processed

# Preview dataset stats
myMem0ry stats --dataset data/processed

# Train model
myMem0ry train --dataset data/processed/train.jsonl --output output/memory_model

# Export to GGUF
myMem0ry export --model output/memory_model --format gguf

# Full pipeline
myMem0ry pipeline --source data/openai/export --output output/memory_model
```

---

## Dependencies

```toml
[project]
name = "mymemory"
version = "0.1.0"
dependencies = [
    "unsloth",
    "unsloth_zoo",
    "torch",
    "transformers",
    "trl",
    "peft",
    "datasets",
    "typer",
    "pydantic",
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "ruff",
]
```

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU VRAM  | 4 GB    | 8+ GB       |
| RAM       | 8 GB    | 16+ GB      |
| Disk      | 10 GB   | 20+ GB      |

Qwen3-0.6B in 4-bit with LoRA fits in ~2GB VRAM for training.

---

## Execution Steps

### 1. Setup
```bash
cd /home/ccsantos/Documents/Projetos/myMem0ry
uv init myMem0ry
uv add unsloth unsloth_zoo torch transformers trl peft datasets typer pydantic
```

### 2. Build Dataset
```bash
python scripts/build_dataset.py --source data/openai/export --output data/processed
```

### 3. Train
```bash
python scripts/train.py --dataset data/processed/train.jsonl --output output/memory_model
```

### 4. Export & Test
```bash
# Export to GGUF
python scripts/export.py --model output/memory_model --format gguf

# Test with Ollama
ollama create mymemory -f Modelfile
ollama run mymemory "What do you know about my projects?"
```

---

## Future Enhancements

- Add Claude and Gemini parsers
- Add synthetic data generation to augment dataset
- Add evaluation metrics (perplexity, memory recall accuracy)
- Add incremental training for new conversations
- Add web UI for dataset management
- Support for larger models (Qwen3-1.7B, 4B, 8B)
- Add RAG layer on top of fine-tuned model for exact recall
