"""Semantic query expansion using model embeddings and FFN walk."""

from __future__ import annotations

import re
from pathlib import Path

import torch
import torch.nn.functional as F

from .search import _STOP_WORDS

_CACHE_DIR = Path("data/.cache/embeddings")

# BPE word-initial tokens (Ġ prefix, like GPT/Qwen) — at least 4 chars after prefix
_BPE_WORD_RE = re.compile(r"^Ġ[a-zA-ZáàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]{4,}$")

# SentencePiece word tokens (no special prefix, like Gemma/Llama) — at least 4 alpha chars
_SP_WORD_RE = re.compile(r"^[a-zA-ZáàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]{4,}$")


def _cache_dir(model_name: str) -> Path:
    """Return the cache directory for a given model."""
    safe = model_name.replace("/", "--")
    return _CACHE_DIR / safe


def _build_word_ids(tokenizer) -> list[int]:
    """Build a list of token IDs that represent real words.

    Auto-detects tokenizer type (BPE vs SentencePiece) based on whether
    the vocabulary contains Ġ-prefixed tokens.
    """
    vocab = tokenizer.get_vocab()

    # Detect tokenizer family by checking for Ġ prefix
    has_g0 = sum(1 for tok in vocab if tok.startswith("Ġ"))
    if has_g0 > 100:
        # BPE tokenizer (GPT, Qwen, etc.) — use Ġ-prefixed tokens
        return [idx for tok, idx in vocab.items() if _BPE_WORD_RE.match(tok)]

    # SentencePiece tokenizer (Gemma, Llama, etc.) — plain alpha tokens
    return [idx for tok, idx in vocab.items() if _SP_WORD_RE.match(tok)]


def _ffn_cache_exists(model_name: str) -> bool:
    """Check if a FFN walk cache exists for the given model."""
    from .ffn_walk import _CACHE_ROOT

    cache = _CACHE_ROOT / model_name.replace("/", "--")
    return (cache / "gate_projs.pt").exists()


class ConceptSearch:
    """Find semantically related tokens.

    Uses FFN walk (gate KNN + down projection) when cache is available,
    falls back to embedding cosine similarity otherwise.
    """

    def __init__(self, model_name: str = "Qwen/Qwen3.5-0.8B") -> None:
        self._model_name = model_name
        self._ffn_cache = None

        # Try FFN walk cache first (LARQL-style)
        if _ffn_cache_exists(model_name):
            from .ffn_walk import FFNCache

            try:
                self._ffn_cache = FFNCache(model_name)
                return
            except Exception:
                pass  # Fall back to embedding approach

        # Fallback: embedding cosine similarity
        cache = _cache_dir(model_name)
        emb_path = cache / "embeddings.pt"
        tok_path = cache / "tokenizer.json"

        if emb_path.exists() and tok_path.exists():
            from tokenizers import Tokenizer

            self._tokenizer = Tokenizer.from_file(str(tok_path))
            self.embeddings = torch.load(emb_path, weights_only=True)
        else:
            # Full load only on first run
            from transformers import AutoModelForCausalLM, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name)
            self.embeddings = model.get_input_embeddings().weight.detach().clone()

            cache.mkdir(parents=True, exist_ok=True)
            torch.save(self.embeddings, emb_path)
            tokenizer.backend_tokenizer.save(str(tok_path))
            self._tokenizer = tokenizer.backend_tokenizer

            del model

        self._word_ids = _build_word_ids(self._tokenizer)

    def similar_tokens(
        self, text: str, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Return the top-k semantically related tokens with scores."""
        if self._ffn_cache is not None:
            results = self._ffn_cache.describe(text, top_k=top_k)
            # Normalize to (token, score) — drop layer info
            return [(tok, sc) for tok, sc, _ly in results]

        return self._similar_tokens_embedding(text, top_k)

    def similar_tokens_with_layers(
        self, text: str, top_k: int = 10
    ) -> list[tuple[str, float, int]]:
        """Return tokens with layer information (FFN walk only)."""
        if self._ffn_cache is not None:
            return self._ffn_cache.describe(text, top_k=top_k)
        # Fallback: no layer info
        return [(tok, sc, -1) for tok, sc in self._similar_tokens_embedding(text, top_k)]

    def _similar_tokens_embedding(self, text: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Fallback: cosine similarity against word tokens in embedding space."""
        token_ids = self._encode(text)
        ids_tensor = torch.tensor(token_ids)
        query_vec = self.embeddings[ids_tensor].mean(dim=0, keepdim=True)

        word_emb = self.embeddings[self._word_ids]
        sims = F.cosine_similarity(query_vec, word_emb)
        k = min(top_k + len(token_ids), len(self._word_ids))
        topk = torch.topk(sims, k)

        results: list[tuple[str, float]] = []
        for idx, score in zip(topk.indices, topk.values):
            token = self._decode(self._word_ids[idx.item()])
            if not token or token.lower() in _STOP_WORDS:
                continue
            results.append((token, score.item()))
            if len(results) == top_k:
                break

        return results

    def _encode(self, text: str) -> list[int]:
        return self._tokenizer.encode(text).ids

    def _decode(self, token_id: int) -> str:
        return self._tokenizer.decode([token_id]).strip()


def expand_query(
    query: str,
    concept_search: ConceptSearch,
    top_k: int = 10,
) -> str:
    """Expand a query with semantically similar tokens.

    Returns the original query plus the top similar tokens found
    in the model's embedding space or FFN knowledge.
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
        if len(t_lower) <= 1:
            continue
        seen.add(t_lower)
        extra_tokens.append(token)

    if not extra_tokens:
        return query

    return f"{query} {' '.join(extra_tokens)}"
