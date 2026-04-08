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
    quantization: str | None = typer.Option(
        None,
        "--quantization",
        help="GGUF quantization method (e.g. q4_k_m, q8_0). If omitted, exports as F16.",
    ),
    patch_modelfile: bool = typer.Option(
        True,
        "--patch-modelfile/--no-patch-modelfile",
        help="Rewrite the Ollama Modelfile FROM line to the GGUF bundle that was just created.",
    ),
) -> None:
    method = quantization or "f16"
    gguf_path = export_model(
        model_dir=model, output_dir=output, quantization_method=quantization
    )
    typer.echo(f"GGUF export saved to {gguf_path} (method={method})")

    if patch_modelfile:
        gguf_dir = Path(f"{output}_gguf")
        modelfile_path = gguf_dir / "Modelfile"
        gguf_file = _primary_gguf(gguf_dir)
        if gguf_file and modelfile_path.exists():
            _update_modelfile(modelfile_path, gguf_file.name)
            typer.echo(f"Updated {modelfile_path} to load {gguf_file.name}")
        elif not gguf_dir.exists():
            typer.echo(
                f"Warning: {gguf_dir} does not exist yet; rerun export before building Ollama",
                err=True,
            )
        elif not gguf_file:
            typer.echo(
                f"Warning: no GGUF bundle found in {gguf_dir}",
                err=True,
            )
        else:
            typer.echo(
                f"Warning: {modelfile_path} is missing; run export again to regenerate it",
                err=True,
            )


def _primary_gguf(directory: Path) -> Path | None:
    try:
        candidates = list(directory.glob("*.gguf"))
    except OSError:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda path: (-_gguf_sort_key(path), path.name))
    return candidates[0]


def _gguf_sort_key(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _update_modelfile(modelfile_path: Path, gguf_filename: str) -> None:
    contents = modelfile_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(contents):
        if line.strip().startswith("FROM "):
            contents[index] = f"FROM {gguf_filename}"
            break
    else:
        contents.insert(0, f"FROM {gguf_filename}")
        
    if not any(line.strip().startswith("PARAMETER presence_penalty") for line in contents):
        contents.append("PARAMETER presence_penalty 1.5")
        
    modelfile_path.write_text("\n".join(contents) + "\n", encoding="utf-8")


if __name__ == "__main__":
    app()
