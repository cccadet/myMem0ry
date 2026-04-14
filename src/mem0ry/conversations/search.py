"""Fast search over conversation .md files using ripgrep."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _check_rg() -> None:
    """Raise if ripgrep is not installed."""
    if not shutil.which("rg"):
        raise FileNotFoundError(
            "ripgrep (rg) not found. Install it: "
            "https://github.com/BurntSushi/ripgrep#installation"
        )


def search(
    query: str,
    conversations_dir: Path,
    top_k: int = 5,
) -> list[Path]:
    """Search conversation files using ripgrep and return paths ranked by match count.

    Args:
        query: Search term(s).
        conversations_dir: Root directory with YYYY-MM-DD subfolders of .md files.
        top_k: Maximum number of files to return.

    Returns:
        List of Path objects sorted by recency (newest date first), then relevance.
    """
    _check_rg()

    if not conversations_dir.exists():
        return []

    # Use ripgrep in count mode to rank by number of matches
    result = subprocess.run(
        [
            "rg",
            "--count",
            "--ignore-case",
            "--no-heading",
            "--glob", "*.md",
            "--max-count", "1000",
            "--sort", "path",
            query,
            str(conversations_dir),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    # Parse output: "filepath:count" lines
    scored: list[tuple[int, Path]] = []
    for line in result.stdout.strip().splitlines():
        parts = line.rsplit(":", 1)
        if len(parts) == 2:
            filepath = Path(parts[0])
            try:
                count = int(parts[1])
            except ValueError:
                count = 1
            scored.append((count, filepath))

    scored.sort(key=lambda x: (x[1].parent.name, x[0]), reverse=True)
    return [path for _, path in scored[:top_k]]
