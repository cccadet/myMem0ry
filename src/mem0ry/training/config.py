"""Training configuration for the LoRA fine-tuning job."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class TrainingConfig:
    model_name: str = "unsloth/Qwen3-0.6B"
    max_seq_length: int = 2048
    load_in_4bit: bool = True
    full_finetune: bool = False
    lora_turbo: bool = False
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
    system_prompt: str = (
        "You are a personal memory assistant with deep knowledge of the user's "
        "past conversations, preferences, projects, and personal history. "
        "Answer questions about the user based on everything you remember from "
        "those conversations. Be specific and reference details when possible."
    )

    qa_backend: str = field(default_factory=lambda: os.environ.get("QA_BACKEND", "api"))
    zai_api_key: str | None = field(
        default_factory=lambda: os.environ.get("ZAI_API_KEY")
    )
    zai_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/"
        )
    )
    qa_generation_model: str = field(
        default_factory=lambda: os.environ.get("QA_GENERATION_MODEL", "glm-4.7-flashx")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )
    )
    ollama_model: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
    )
    llamacpp_model_path: str = field(
        default_factory=lambda: os.environ.get("LLAMACPP_MODEL_PATH", "")
    )
    llamacpp_n_gpu_layers: int = field(
        default_factory=lambda: int(os.environ.get("LLAMACPP_N_GPU_LAYERS", "-1"))
    )
    llamacpp_n_ctx: int = field(
        default_factory=lambda: int(os.environ.get("LLAMACPP_N_CTX", "4096"))
    )
    qa_pairs_per_conversation: int = 4
    qa_cache_path: str = "data/qa_cache.jsonl"
    enable_qa_generation: bool = True
    use_temporal: bool = True
