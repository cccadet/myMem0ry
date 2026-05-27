"""BM25 search backend using rank-bm25 library."""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from .search import _STOP_WORDS

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 indexing."""
    return [
        w
        for w in re.findall(r"\w+", text.lower())
        if w not in _STOP_WORDS and len(w) > 1
    ]


def _index_path(conversations_dir: Path) -> Path:
    return conversations_dir / ".bm25_index.pkl"


def build_bm25_index(conversations_dir: Path) -> None:
    """Build and save BM25 index from all .md files in conversations_dir."""
    files = sorted(conversations_dir.rglob("*.md"))
    if not files:
        logger.info("[bm25] Nenhum arquivo .md encontrado.")
        return

    corpus: list[list[str]] = []
    paths: list[Path] = []

    for f in files:
        text = f.read_text(encoding="utf-8")
        tokens = _tokenize(text)
        if tokens:
            corpus.append(tokens)
            paths.append(f)

    bm25 = BM25Okapi(corpus)

    path = _index_path(conversations_dir)
    with open(path, "wb") as fh:
        pickle.dump({"bm25": bm25, "paths": paths}, fh)

    logger.info("[bm25] Índice criado: %d arquivos em %s", len(paths), path)


def search_bm25(
    query: str,
    conversations_dir: Path,
    top_k: int = 5,
) -> list[Path]:
    """Search conversations using BM25 ranking.

    Builds index on-the-fly if not cached.
    """
    path = _index_path(conversations_dir)

    if not path.exists():
        build_bm25_index(conversations_dir)

    with open(path, "rb") as fh:
        data = pickle.load(fh)

    bm25: BM25Okapi = data["bm25"]
    paths: list[Path] = data["paths"]

    tokenized_query = _tokenize(query)
    if not tokenized_query:
        return []

    scores = bm25.get_scores(tokenized_query)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    return [paths[i] for i, _ in ranked[:top_k]]
