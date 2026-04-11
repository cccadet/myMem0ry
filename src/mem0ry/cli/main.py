"""Typer CLI for the myMem0ry pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from ..pipeline.dataset import build_dataset_from_openai
from ..training.config import TrainingConfig
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
):
    """Parse exports and produce ChatML JSONL datasets."""

    if qa_backend == "turns":
        enable_qa = True
    else:
        enable_qa = not no_qa

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
        enable_qa_generation=enable_qa,
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
    full_finetune: bool = typer.Option(
        False,
        "--full-finetune",
        help="Full fine-tuning without LoRA (pure memorization mode).",
    ),
    lora_turbo: bool = typer.Option(
        False,
        "--lora-turbo",
        help="LoRA with high-rank memorization preset (r=128, alpha=256, lr=1e-3, 50 epochs).",
    ),
    epochs: int = typer.Option(
        3,
        "--epochs",
        help="Number of training epochs (ignored if --full-finetune, min 20).",
    ),
    learning_rate: float = typer.Option(
        2e-4, "--lr", help="Learning rate (ignored if --full-finetune, uses 5e-4)."
    ),
):
    """Train the model on the fine-tuning dataset (LoRA by default, or full fine-tune)."""

    config = TrainingConfig(
        full_finetune=full_finetune,
        lora_turbo=lora_turbo,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
    )
    model_dir = train_model(dataset_path=dataset, output_dir=output, config=config)
    typer.echo(f"Model stored in {model_dir}")


@app.command()
def export(
    model: Path = typer.Option(
        None,
        "--model",
        help="Path to the trained model directory. Auto-detects LoRA or full fine-tune output.",
    ),
    output: Path = Path("output/memory_model"),
    quantization: str | None = typer.Option(
        None,
        "--quantization",
        help="GGUF quantization method (e.g. q4_k_m, q8_0). If omitted, exports as F16 (no quantization loss).",
    ),
):
    """Export the trained model to a GGUF bundle (F16 by default)."""

    if model is None:
        full_path = output / "memory_model_full"
        lora_path = output / "memory_model_lora"
        model = full_path if full_path.exists() else lora_path

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
    full_finetune: bool = typer.Option(
        False, "--full-finetune", help="Full fine-tuning without LoRA."
    ),
    lora_turbo: bool = typer.Option(
        False, "--lora-turbo", help="LoRA high-rank memorization preset."
    ),
) -> None:
    """Execute the full pipeline: dataset → train → export."""

    build(source=source, output=processed)
    train(
        dataset=processed / "train.jsonl",
        output=model_output,
        full_finetune=full_finetune,
        lora_turbo=lora_turbo,
    )
    export(output=gguf_output)
