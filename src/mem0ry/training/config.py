"""Training configuration for the LoRA fine-tuning job."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class TrainingConfig:
    model_name: str = "unsloth/Qwen3-0.6B-unsloth-bnb-4bit"
    max_seq_length: int = 2048
    load_in_4bit: bool = True
    lora_r: int = 32
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    target_modules: Sequence[str] = field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )
    batch_size: int = 2
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 5
    max_steps: int = -1
    num_train_epochs: int = 3
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    fp16: bool = True
    optim: str = "adamw_8bit"
    lr_scheduler_type: str = "cosine"
    seed: int = 42
