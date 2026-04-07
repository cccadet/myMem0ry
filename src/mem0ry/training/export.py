"""Helpers to export a fine-tuned LoRA model to GGUF."""

from __future__ import annotations

from pathlib import Path

from unsloth import FastLanguageModel

from ..utils.logging import configure_logging
from ..utils.paths import ensure_dir

LOGGER = configure_logging()


def export_model(
    model_dir: Path,
    output_dir: Path,
    *,
    quantization_method: str = "q4_k_m",
) -> Path:
    """Export the fine-tuned weights to a GGUF bundle."""

    model_dir = model_dir.expanduser()
    output_dir = ensure_dir(output_dir.expanduser())

    LOGGER.info("Loading fine-tuned model from %s", model_dir)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(model_dir),
        max_seq_length=2048,
        load_in_4bit=True,
    )

    LOGGER.info("Exporting GGUF bundle to %s", output_dir)
    model.save_pretrained_gguf(
        str(output_dir), tokenizer, quantization_method=quantization_method
    )
    return output_dir
