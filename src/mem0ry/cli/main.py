"""Typer CLI for the myMem0ry pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ..pipeline.dataset import build_dataset_from_openai
from ..training.export import export_model
from ..training.train import train_model

app = typer.Typer(help="myMem0ry fine-tuning toolkit")


@app.command()
def build(
    source: Path = Path("data/openai/export"),
    output: Path = Path("data/processed"),
    system_prompt: str | None = None,
    max_seq_length: int = 2048,
    val_ratio: float = 0.05,
    overlap_turns: int = 2,
    min_turns: int = 2,
):
    """Parse exports and produce ChatML JSONL datasets."""

    result = build_dataset_from_openai(
        source=source,
        output=output,
        system_prompt=system_prompt,
        max_seq_length=max_seq_length,
        overlap_turns=overlap_turns,
        min_turns=min_turns,
        val_ratio=val_ratio,
    )
    typer.echo("Dataset built")
    typer.echo(json.dumps(result["stats"], indent=2))


@app.command()
def stats(target: Path = Path("data/processed/stats.json")) -> None:
    """Print dataset statistics."""

    path = target if target.is_file() else target / "stats.json"
    if not path.exists():
        raise typer.BadParameter(f"Stats file not found at {path}")
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def train(
    dataset: Path = Path("data/processed/train.jsonl"),
    output: Path = Path("output/memory_model"),
):
    """Train the LoRA adapters on the fine-tuning dataset."""

    model_dir = train_model(dataset_path=dataset, output_dir=output)
    typer.echo(f"Model stored in {model_dir}")


@app.command()
def export(
    model: Path = Path("output/memory_model/memory_model_lora"),
    output: Path = Path("output/memory_model"),
    quantization: str = "q4_k_m",
):
    """Export the trained model to a GGUF bundle."""

    bundle = export_model(
        model_dir=model, output_dir=output, quantization_method=quantization
    )
    typer.echo(f"GGUF bundle created at {bundle}")


@app.command()
def pipeline(
    source: Path = Path("data/openai/export"),
    processed: Path = Path("data/processed"),
    model_output: Path = Path("output/memory_model"),
    gguf_output: Path = Path("output/memory_model"),
) -> None:
    """Execute the full pipeline: dataset → train → export."""

    build(source=source, output=processed)
    train(dataset=processed / "train.jsonl", output=model_output)
    export(model=model_output / "memory_model_lora", output=gguf_output)
