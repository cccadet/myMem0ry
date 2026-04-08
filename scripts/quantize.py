"""CLI entrypoint to quantize an existing F16 GGUF file."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(help="Quantize an F16 GGUF file using llama.cpp")


@app.command()
def main(
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
    if not input_gguf.exists():
        typer.echo(f"Error: Input GGUF not found: {input_gguf}", err=True)
        raise typer.Exit(code=1)

    if input_gguf.suffix != ".gguf":
        typer.echo("Error: Input file must be a .gguf file", err=True)
        raise typer.Exit(code=1)

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

    typer.echo(f"Quantizing {input_gguf} -> {output} (method={method})")
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


if __name__ == "__main__":
    app()
