"""Semantic query expansion using model embeddings."""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn.functional as F

from .search import _STOP_WORDS

_CACHE_DIR = Path("data/.cache/embeddings")


def _cache_dir(model_name: str) -> Path:
    """Return the cache directory for a given model."""
    safe = model_name.replace("/", "--")
    return _CACHE_DIR / safe


class ConceptSearch:
    """Find semantically similar tokens using a model's embedding matrix.

    Caches embeddings + tokenizer to disk after the first load so subsequent
    runs skip the heavy model download entirely.
    """

    def __init__(self, model_name: str = "Qwen/Qwen3.5-0.8B") -> None:
        cache = _cache_dir(model_name)
        emb_path = cache / "embeddings.pt"
        tok_path = cache / "tokenizer.json"

        if emb_path.exists() and tok_path.exists():
            from tokenizers import Tokenizer

            self._tokenizer = Tokenizer.from_file(str(tok_path))
            self.embeddings = torch.load(emb_path, weights_only=True)
            return

        # Full load only on first run
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)
        self.embeddings = model.get_input_embeddings().weight.detach().clone()

        # Save tokenizer as standalone tokenizer.json (fast to load via `tokenizers` lib)
        cache.mkdir(parents=True, exist_ok=True)
        torch.save(self.embeddings, emb_path)
        tokenizer.backend_tokenizer.save(str(tok_path))
        self._tokenizer = tokenizer.backend_tokenizer

        del model

    def _encode(self, text: str) -> list[int]:
        return self._tokenizer.encode(text).ids

    def _decode(self, token_id: int) -> str:
        return self._tokenizer.decode([token_id]).strip()

    def similar_tokens(self, text: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Return the top-k tokens most similar to the input text.

        Computes the mean embedding of the input tokens, then finds the
        closest tokens in the embedding space via cosine similarity.
        """
        token_ids = self._encode(text)
        ids_tensor = torch.tensor(token_ids)
        query_vec = self.embeddings[ids_tensor].mean(dim=0, keepdim=True)
        sims = F.cosine_similarity(query_vec, self.embeddings)
        topk = torch.topk(sims, top_k + len(token_ids))

        results: list[tuple[str, float]] = []
        for idx, score in zip(topk.indices, topk.values):
            token = self._decode(idx.item())
            if not token or token in _STOP_WORDS:
                continue
            results.append((token, score.item()))
            if len(results) == top_k:
                break

        return results


def expand_query(
    query: str,
    concept_search: ConceptSearch,
    top_k: int = 10,
) -> str:
    """Expand a query with semantically similar tokens.

    Returns the original query plus the top similar tokens found
    in the model's embedding space.
    """
    similar = concept_search.similar_tokens(query, top_k=top_k)

    # Collect unique tokens that aren't already in the query
    query_lower = query.lower()
    extra_tokens: list[str] = []
    seen: set[str] = set()

    for token, _ in similar:
        t_lower = token.lower()
        if t_lower in seen or t_lower in query_lower:
            continue
        # Skip tokens that are just punctuation or single chars
        if len(t_lower) <= 1:
            continue
        seen.add(t_lower)
        extra_tokens.append(token)

    if not extra_tokens:
        return query

    return f"{query} {' '.join(extra_tokens)}"
