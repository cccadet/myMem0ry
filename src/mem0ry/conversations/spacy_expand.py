"""Query expansion using spaCy word vectors — word-level, no subword noise."""

from __future__ import annotations

import numpy as np
import spacy


class SpacyConceptSearch:
    """Find semantically related words using spaCy word vectors.

    Operates at the word level by design — no BPE subword fragmentation.
    Uses pre-computed normalized vocab matrix for fast cosine similarity.
    """

    def __init__(self, model_name: str = "pt_core_news_lg") -> None:
        self._nlp = spacy.load(model_name)
        self._build_vocab_matrix()

    def _build_vocab_matrix(self) -> None:
        """Build a normalized matrix of all vocab vectors for fast lookup.

        Iterates over the vector store (not nlp.vocab lexemes) to access
        all 500K+ word vectors in the model.
        """
        keys = list(self._nlp.vocab.vectors.keys())
        data = self._nlp.vocab.vectors.data  # (N, 300)

        words: list[str] = []
        indices: list[int] = []
        for i, key in enumerate(keys):
            word = self._nlp.vocab.strings[key]
            if not word.isalpha() or len(word) < 4:
                continue
            words.append(word.lower())
            indices.append(i)

        self._vocab_words = np.array(words)
        mat = data[indices].astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._vocab_matrix = mat / norms

    def similar_tokens(
        self, text: str, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Return the top-k semantically related words with cosine scores."""
        doc = self._nlp(text)
        vecs = [t.vector for t in doc if t.has_vector]
        if not vecs:
            return []

        query = np.mean(vecs, axis=0).astype(np.float32)
        norm = np.linalg.norm(query)
        if norm == 0:
            return []
        query = query / norm

        sims = self._vocab_matrix @ query
        # Exclude query words and their morphological variants (shared prefix)
        query_lower = {t.text.lower() for t in doc}
        prefixes = {w[:4] for w in query_lower if len(w) >= 4}
        for i, w in enumerate(self._vocab_words):
            if w in query_lower:
                sims[i] = -2.0
            elif any(w.startswith(p) for p in prefixes):
                sims[i] = -1.5

        top_indices = np.argsort(sims)[::-1]
        seen: set[str] = set()
        results: list[tuple[str, float]] = []

        for idx in top_indices:
            word = self._vocab_words[idx]
            if word in seen:
                continue
            seen.add(word)
            results.append((word, float(sims[idx])))
            if len(results) == top_k:
                break

        return results

    def similar_tokens_with_layers(
        self, text: str, top_k: int = 10, **kwargs,
    ) -> list[tuple[str, float, int]]:
        """Same as similar_tokens but with placeholder layer info for CLI compat."""
        return [(tok, sc, -1) for tok, sc in self.similar_tokens(text, top_k)]


def expand_query_spacy(
    query: str,
    concept_search: SpacyConceptSearch,
    top_k: int = 10,
) -> str:
    """Expand a query with semantically similar words using spaCy vectors."""
    similar = concept_search.similar_tokens(query, top_k=top_k)

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
