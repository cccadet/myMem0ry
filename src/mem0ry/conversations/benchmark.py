"""Benchmark pipeline comparing search backends."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .search import search
from .search_bm25 import search_bm25
from .search_fts import search_fts

logger = logging.getLogger(__name__)


def run_benchmark(
    query: str,
    conversations_dir: Path,
    top_k: int = 3,
    encoder=None,
    vec_store=None,
) -> list[dict[str, Any]]:
    """Run query across all backends and collect timing + results.

    Returns a list of dicts with keys: backend, time_ms, n_files, paths.
    """
    from .search_hybrid import search_hybrid

    backends: list[tuple[str, Callable[..., list[Path]]]] = [
        ("ripgrep", search),
        ("bm25", search_bm25),
        ("fts5", search_fts),
    ]

    if encoder is not None and vec_store is not None:
        def _hybrid_fn(q: str, d: Path, top_k: int = top_k) -> list[Path]:
            return search_hybrid(q, d, encoder, vec_store, top_k=top_k)
        backends.append(("hybrid", _hybrid_fn))

    results = []

    for name, search_fn in backends:
        t0 = time.perf_counter()
        try:
            paths = search_fn(query, conversations_dir, top_k=top_k)
            elapsed = (time.perf_counter() - t0) * 1000
        except Exception as e:
            elapsed = -1
            paths = []
            logger.warning("[benchmark] %s falhou: %s", name, e)

        results.append({
            "backend": name,
            "time_ms": round(elapsed, 1),
            "n_files": len(paths),
            "paths": paths,
        })

    return results


def format_table(results: list[dict[str, Any]]) -> str:
    """Format benchmark results as a terminal table."""
    header = f"{'Backend':<10} {'Tempo (ms)':>10} {'Arquivos':>9}  Top match"
    sep = "-" * len(header)
    lines = [header, sep]

    for r in results:
        top = r["paths"][0].name if r["paths"] else "-"
        lines.append(
            f"{r['backend']:<10} {r['time_ms']:>10.1f} {r['n_files']:>9}  {top}"
        )

    return "\n".join(lines)
