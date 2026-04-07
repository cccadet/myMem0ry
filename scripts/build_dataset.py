"""CLI entrypoint to build the fine-tuning dataset."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import typer

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

build_dataset_from_openai = importlib.import_module(
    "mem0ry.pipeline.dataset"
).build_dataset_from_openai

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
) -> None:
    result = build_dataset_from_openai(
        source=source,
        output=output,
        system_prompt=system_prompt,
        max_seq_length=max_seq_length,
        overlap_turns=overlap_turns,
        min_turns=min_turns,
        val_ratio=val_ratio,
    )
    typer.echo("Dataset ready")
    typer.echo(json.dumps(result["stats"], indent=2))


if __name__ == "__main__":
    app()
