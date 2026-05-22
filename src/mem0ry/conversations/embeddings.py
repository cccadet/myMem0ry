"""Generate embeddings from text using spaCy word vectors (300-dim)."""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import spacy

logger = logging.getLogger(__name__)


class SpacyEncoder:
    """Encode text into fixed-size vectors using spaCy doc vectors.

    Uses the pre-loaded spaCy model's doc.vector (mean of token vectors),
    producing a 300-dimensional float32 embedding per text.

    Usage::

        encoder = SpacyEncoder("pt_core_news_lg")
        vec = encoder.encode("Python é uma linguagem de programação")
        assert vec.shape == (300,)
    """

    def __init__(self, model_name: str = "pt_core_news_lg") -> None:
        self._nlp = spacy.load(model_name)
        self._dim = self._nlp.vocab.vectors.shape[1]

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, text: str) -> np.ndarray:
        """Return a (dim,) float32 vector for *text*. Zero vector if empty."""
        if not text.strip():
            return np.zeros(self._dim, dtype=np.float32)

        doc = self._nlp(text)
        vec = np.array(doc.vector, dtype=np.float32)
        return vec

    def encode_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (N, dim) float32 matrix. One row per text."""
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)

        matrix = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, doc in enumerate(self._nlp.pipe(texts)):
            matrix[i] = doc.vector.astype("float32")
        return matrix
