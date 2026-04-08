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
    quantization: str | None = typer.Option(
        None,
        "--quantization",
        help="GGUF quantization method (e.g. q4_k_m, q8_0). If omitted, exports as F16 (no quantization loss).",
    ),
):
    """Export the trained model to a GGUF bundle (F16 by default)."""

    bundle = export_model(
        model_dir=model, output_dir=output, quantization_method=quantization
    )
    method = quantization or "f16"
    typer.echo(f"GGUF bundle created at {bundle} (method={method})")


@app.command()
def quantize(
    input_gguf: Path = typer.Argument(
        ...,
        help="Path to the F16 GGUF file to quantize.",
    ),
    method: str = typer.Option(
        "q4_k_m",
        "--method",
        help="Quantization method (e.g. q4_k_m, q8_0, q5_k_m).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Output path for the quantized GGUF. Defaults to same directory as input.",
    ),
) -> None:
    """Quantize an existing F16 GGUF file using llama.cpp."""

    import subprocess
    import shutil

    if not input_gguf.exists():
        raise typer.BadParameter(f"Input GGUF not found: {input_gguf}")

    if not input_gguf.suffix == ".gguf":
        raise typer.BadParameter("Input file must be a .gguf file")

    if output is None:
        stem = input_gguf.stem
        output = input_gguf.parent / f"{stem}.{method.upper()}.gguf"

    quantize_bin = shutil.which("llama-quantize")
    if quantize_bin is None:
        quantize_bin = shutil.which("quantize")
    if quantize_bin is None:
        typer.echo(
            "Error: llama-quantize not found in PATH.\n"
            "Install llama.cpp: https://github.com/ggerganov/llama.cpp\n"
            "Or re-export the model with --quantization to quantize directly.",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(f"Quantizing {input_gguf} → {output} (method={method})")
    result = subprocess.run(
        [quantize_bin, str(input_gguf), str(output), method],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"Quantization failed:\n{result.stderr}", err=True)
        raise typer.Exit(code=1)

    typer.echo(result.stdout)
    typer.echo(f"Quantized GGUF saved to {output}")


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
