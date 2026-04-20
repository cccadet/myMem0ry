"""Benchmark pipeline comparing search backends."""

from __future__ import annotations

import time
from pathlib import Path

from .search import search
from .search_bm25 import search_bm25
from .search_fts import search_fts


def run_benchmark(
    query: str,
    conversations_dir: Path,
    top_k: int = 3,
) -> list[dict]:
    """Run query across all backends and collect timing + results.

    Returns a list of dicts with keys: backend, time_ms, n_files, paths.
    """
    backends = [
        ("ripgrep", search),
        ("bm25", search_bm25),
        ("fts5", search_fts),
    ]

    results = []

    for name, search_fn in backends:
        t0 = time.perf_counter()
        try:
            paths = search_fn(query, conversations_dir, top_k=top_k)
            elapsed = (time.perf_counter() - t0) * 1000
        except Exception as e:
            elapsed = -1
            paths = []
            print(f"[benchmark] {name} falhou: {e}")

        results.append({
            "backend": name,
            "time_ms": round(elapsed, 1),
            "n_files": len(paths),
            "paths": paths,
        })

    return results


def format_table(results: list[dict]) -> str:
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
