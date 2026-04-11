"""Training helpers that orchestrate FastLanguageModel + LoRA."""

from __future__ import annotations

from pathlib import Path

import torch
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

    LOGGER.info("Loading base model %s", config.model_name)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.model_name,
        max_seq_length=config.max_seq_length,
        load_in_4bit=config.load_in_4bit if not config.full_finetune else False,
        dtype=None,
    )
    if config.full_finetune:
        LOGGER.info("Converting model to float16 for fp16 training")
        model = model.to(torch.float16)
    tokenizer = get_chat_template(tokenizer, chat_template="qwen3")

    LOGGER.info("Preparing dataset %s", dataset_path)
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    format_fn = _make_formatting_func(tokenizer, config.system_prompt)
    dataset = dataset.map(format_fn, batched=True, remove_columns=dataset.column_names)

    if config.full_finetune:
        LOGGER.info(
            "Full fine-tuning mode — dtype=%s, skipping LoRA",
            next(model.parameters()).dtype,
        )
    elif config.lora_turbo:
        model = FastLanguageModel.get_peft_model(
            model,
            r=128,
            target_modules=list(config.target_modules),
            lora_alpha=256,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )
        LOGGER.info("LoRA turbo mode — r=128, alpha=256")
    else:
        model = FastLanguageModel.get_peft_model(
            model,
            r=config.lora_r,
            target_modules=list(config.target_modules),
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )

    lr = config.learning_rate
    epochs = config.num_train_epochs
    optim = config.optim
    fp16 = config.fp16
    batch_size = config.batch_size
    grad_accum = config.gradient_accumulation_steps
    grad_ckpt = False
    if config.full_finetune:
        lr = 5e-4
        epochs = max(epochs, 20)
        optim = "adamw_torch"
        batch_size = 1
        grad_accum = 8
        grad_ckpt = True
        fp16 = True
    elif config.lora_turbo:
        lr = max(lr, 1e-3)
        epochs = max(epochs, 50)
        optim = "adamw_torch"

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        gradient_checkpointing=grad_ckpt,
        warmup_steps=config.warmup_steps,
        max_steps=config.max_steps,
        num_train_epochs=epochs,
        learning_rate=lr,
        weight_decay=config.weight_decay,
        fp16=fp16,
        bf16=False,
        max_grad_norm=0,
        optim=optim,
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
    model_dir = output_dir / (
        "memory_model_full" if config.full_finetune else "memory_model_lora"
    )
    ensure_dir(model_dir)
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)

    LOGGER.info("Model saved to %s", model_dir)
    return model_dir


def _make_formatting_func(tokenizer, system_prompt: str):
    """Return a batched formatting function that uses the Qwen3 chat template."""

    def _format(batch: dict) -> dict[str, list[str]]:
        texts: list[str] = []
        for messages in batch.get("messages", []):
            msgs = list(messages)
            if msgs and msgs[0].get("role") != "system":
                msgs.insert(0, {"role": "system", "content": system_prompt})
            text = tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=False
            )
            texts.append(text)
        return {"text": texts}

    return _format
