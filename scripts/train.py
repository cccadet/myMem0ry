"""CLI entrypoint to train the LoRA weights."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import typer

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

train_model = importlib.import_module("mem0ry.training.train").train_model

app = typer.Typer(help="Train the Qwen3-0.6B model with LoRA")


@app.command()
def main(
    dataset: Path = Path("data/processed/train.jsonl"),
    output: Path = Path("output/memory_model"),
) -> None:
    model_path = train_model(dataset_path=dataset, output_dir=output)
    typer.echo(f"Training complete. Checkpoint written to {model_path}")


if __name__ == "__main__":
    app()
