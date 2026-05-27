"""Fast search over conversation .md files using ripgrep."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

# Common Portuguese stop words to filter from queries
_STOP_WORDS = frozenset(
    "a ao aos aquela aquele as assim até com como da de dei do e em essa esse "
    "esta esse eu fez foi falei já mais mas me meu minha minhas meus na não no "
    "nos o os ou para pela pelo por que quem se sobre um uma umas uns".split()
)


def _extract_keywords(query: str) -> list[str]:
    """Extract relevant search keywords from a natural language query."""
    words = re.findall(r"[a-zA-Z0-9áàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]+", query)
    return [w for w in words if w.lower() not in _STOP_WORDS and len(w) > 1]


def _check_rg() -> None:
    """Raise if ripgrep is not installed."""
    if not shutil.which("rg"):
        raise FileNotFoundError(
            "ripgrep (rg) not found in PATH. Install it: "
            "https://github.com/BurntSushi/ripgrep#installation — "
            "search() requires rg to perform keyword search."
        )


def search(
    query: str,
    conversations_dir: Path,
    top_k: int = 5,
) -> list[Path]:
    """Search conversation files using ripgrep and return paths ranked by match count.

    Extracts keywords from the query and searches for any of them,
    ranking files by total match count.

    Args:
        query: Natural language search query.
        conversations_dir: Root directory with YYYY-MM-DD subfolders of .md files.
        top_k: Maximum number of files to return.

    Returns:
        List of Path objects sorted by recency (newest date first), then relevance.
    """
    _check_rg()

    if not conversations_dir.exists():
        return []

    keywords = _extract_keywords(query)
    if not keywords:
        return []

    # Build ripgrep pattern: match any keyword
    pattern = "|".join(re.escape(kw) for kw in keywords)

    result = subprocess.run(
        [
            "rg",
            "--count",
            "--ignore-case",
            "--no-heading",
            "--glob",
            "*.md",
            "--max-count",
            "1000",
            "--sort",
            "path",
            pattern,
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
