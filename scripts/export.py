"""CLI entrypoint to export a GGUF bundle."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import typer

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

export_model = importlib.import_module("mem0ry.training.export").export_model

app = typer.Typer(help="Export fine-tuned model to GGUF")


@app.command()
def main(
    model: Path = Path("output/memory_model/memory_model_lora"),
    output: Path = Path("output/memory_model"),
    quantization: str = "q4_k_m",
) -> None:
    gguf_path = export_model(
        model_dir=model, output_dir=output, quantization_method=quantization
    )
    typer.echo(f"GGUF export saved to {gguf_path}")


if __name__ == "__main__":
    app()
