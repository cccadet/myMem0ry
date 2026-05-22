"""Hybrid search combining BM25 and vector similarity via RRF fusion."""

from __future__ import annotations

from pathlib import Path

from .search_bm25 import search_bm25
from .vector_store import VectorStore
from .embeddings import SpacyEncoder


def _rrf_fuse(
    *ranked_lists: list[str],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over multiple ranked lists of paths.

    Each *ranked_lists[i]* is a list of path strings ordered by relevance.
    RRF score: sum(1 / (k + rank_j)) for each list j.
    """
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, path in enumerate(lst):
            scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def search_hybrid(
    query: str,
    conversations_dir: Path,
    encoder: SpacyEncoder,
    vec_store: VectorStore,
    top_k: int = 5,
    rrf_k: int = 60,
) -> list[Path]:
    """Search combining BM25 text ranking + vector cosine similarity via RRF.

    Returns up to *top_k* Path objects ranked by fused score.
    """
    bm25_paths = search_bm25(query, conversations_dir, top_k=top_k * 3)
    bm25_strs = [str(p.relative_to(conversations_dir)) for p in bm25_paths]

    query_vec = encoder.encode(query)
    vec_results = vec_store.query(query_vec, top_k=top_k * 3)
    vec_strs = [path for path, _ in vec_results]

    fused = _rrf_fuse(bm25_strs, vec_strs, k=rrf_k)

    results: list[Path] = []
    for rel_path, _ in fused[:top_k]:
        full = conversations_dir / rel_path
        if full.exists():
            results.append(full)
    return results
