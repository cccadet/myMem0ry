"""Path helpers used across the project."""

from __future__ import annotations

from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
