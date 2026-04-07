"""Training helpers that orchestrate FastLanguageModel + LoRA."""

from __future__ import annotations

from pathlib import Path

from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template

from .config import TrainingConfig
from ..utils.logging import configure_logging
from ..utils.paths import ensure_dir

LOGGER = configure_logging()


def train_model(
    dataset_path: Path,
    output_dir: Path,
    *,
    config: TrainingConfig | None = None,
) -> Path:
    """Train the LoRA weights for the personal memory model."""

    config = config or TrainingConfig()
    LOGGER.info("Preparing dataset %s", dataset_path)

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    dataset = dataset.map(
        _formatting_func, batched=True, remove_columns=dataset.column_names
    )

    LOGGER.info("Loading base model %s", config.model_name)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.model_name,
        max_seq_length=config.max_seq_length,
        load_in_4bit=config.load_in_4bit,
    )
    tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

    model = FastLanguageModel.get_peft_model(
        model,
        r=config.lora_r,
        target_modules=list(config.target_modules),
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        warmup_steps=config.warmup_steps,
        max_steps=config.max_steps,
        num_train_epochs=config.num_train_epochs,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        fp16=config.fp16,
        optim=config.optim,
        lr_scheduler_type=config.lr_scheduler_type,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        seed=config.seed,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=config.max_seq_length,
        args=training_args,
    )

    trainer.train()

    ensure_dir(output_dir)
    model_dir = output_dir / "memory_model_lora"
    ensure_dir(model_dir)
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)

    LOGGER.info("Model saved to %s", model_dir)
    return model_dir


def _formatting_func(batch: dict) -> dict[str, list[str]]:
    texts: list[str] = []
    for messages in batch.get("messages", []):
        formatted = "\n".join(
            f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages
        )
        texts.append(formatted)
    return {"text": texts}
