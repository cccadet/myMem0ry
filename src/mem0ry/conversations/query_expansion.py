"""Semantic query expansion using model embeddings."""

from __future__ import annotations

from transformers import AutoModelForCausalLM, AutoTokenizer

import torch
import torch.nn.functional as F

from .search import _STOP_WORDS


class ConceptSearch:
    """Find semantically similar tokens using a model's embedding matrix."""

    def __init__(self, model_name: str = "Qwen/Qwen3.5-0.8B"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.embeddings = self.model.get_input_embeddings().weight.detach()

    def similar_tokens(self, text: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Return the top-k tokens most similar to the input text.

        Computes the mean embedding of the input tokens, then finds the
        closest tokens in the embedding space via cosine similarity.
        """
        inputs = self.tokenizer(text, return_tensors="pt")
        token_ids = inputs["input_ids"][0]

        query_vec = self.embeddings[token_ids].mean(dim=0, keepdim=True)
        sims = F.cosine_similarity(query_vec, self.embeddings)
        topk = torch.topk(sims, top_k + len(token_ids))

        results: list[tuple[str, float]] = []
        for idx, score in zip(topk.indices, topk.values):
            token = self.tokenizer.decode([idx.item()]).strip()
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
