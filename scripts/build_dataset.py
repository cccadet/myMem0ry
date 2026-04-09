"""CLI entrypoint to build the fine-tuning dataset."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Optional

import typer

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

build_dataset_from_openai = importlib.import_module(
    "mem0ry.pipeline.dataset"
).build_dataset_from_openai

TrainingConfig = importlib.import_module("mem0ry.training.config").TrainingConfig

app = typer.Typer(help="Build ChatML training datasets from OpenAI exports")


@app.command()
def main(
    source: Path = Path("data/openai/export"),
    output: Path = Path("data/processed"),
    system_prompt: str | None = None,
    max_seq_length: int = 2048,
    val_ratio: float = 0.05,
    overlap_turns: int = 2,
    min_turns: int = 2,
    qa_backend: str = "api",
    qa_model: str = "glm-4.7-flashx",
    ollama_model: str = "qwen3:0.6b",
    ollama_url: str = "http://localhost:11434/v1",
    llamacpp_model: str = "",
    llamacpp_gpu_layers: int = -1,
    llamacpp_ctx: int = 4096,
    qa_pairs: int = 4,
    qa_cache: str = "data/qa_cache.jsonl",
    force_qa: bool = False,
    regen_qa: Optional[list[str]] = None,
    no_qa: bool = False,
    no_temporal: bool = False,
) -> None:
    config = TrainingConfig(
        qa_backend=qa_backend,
        qa_generation_model=qa_model,
        ollama_model=ollama_model,
        ollama_base_url=ollama_url,
        llamacpp_model_path=llamacpp_model,
        llamacpp_n_gpu_layers=llamacpp_gpu_layers,
        llamacpp_n_ctx=llamacpp_ctx,
        qa_pairs_per_conversation=qa_pairs,
        qa_cache_path=qa_cache,
        enable_qa_generation=not no_qa,
        use_temporal=not no_temporal,
    )

    result = build_dataset_from_openai(
        source=source,
        output=output,
        system_prompt=system_prompt,
        max_seq_length=max_seq_length,
        overlap_turns=overlap_turns,
        min_turns=min_turns,
        val_ratio=val_ratio,
        config=config,
        force_qa=force_qa,
        regen_qa_ids=regen_qa,
    )
    typer.echo("Dataset ready")
    typer.echo(json.dumps(result["stats"], indent=2))


if __name__ == "__main__":
    app()
