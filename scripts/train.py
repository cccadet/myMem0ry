"""CLI entrypoint to train the model (LoRA or full fine-tuning)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import typer

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

train_model = importlib.import_module("mem0ry.training.train").train_model
TrainingConfig = importlib.import_module("mem0ry.training.config").TrainingConfig

app = typer.Typer(help="Train the Qwen3-0.6B model")


@app.command()
def main(
    dataset: Path = Path("data/processed/train.jsonl"),
    output: Path = Path("output/memory_model"),
    full_finetune: bool = typer.Option(
        False,
        "--full-finetune",
        help="Full fine-tuning without LoRA (memorization mode).",
    ),
    lora_turbo: bool = typer.Option(
        False,
        "--lora-turbo",
        help="LoRA with high-rank memorization preset (r=128, lr=1e-3, 50 epochs).",
    ),
    epochs: int = typer.Option(3, "--epochs", help="Training epochs."),
    lr: float = typer.Option(2e-4, "--lr", help="Learning rate."),
) -> None:
    config = TrainingConfig(
        full_finetune=full_finetune,
        lora_turbo=lora_turbo,
        num_train_epochs=epochs,
        learning_rate=lr,
    )
    model_path = train_model(dataset_path=dataset, output_dir=output, config=config)
    typer.echo(f"Training complete. Checkpoint written to {model_path}")


if __name__ == "__main__":
    app()
