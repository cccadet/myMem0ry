"""Shared encoder protocol for vector search."""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

import numpy as np


@runtime_checkable
class TextEncoder(Protocol):
    """Protocol for text-to-vector encoders used by the vector store.

    Any implementation must expose its output dimension and be able to
    encode a single text or a batch of texts into float32 vectors.

    Usage::

        encoder: TextEncoder = get_encoder(config)
        vec = encoder.encode("Python")
        assert vec.shape == (encoder.dim,)
    """

    @property
    def dim(self) -> int:
        """Return the embedding dimensionality."""
        ...

    def encode(self, text: str) -> np.ndarray:
        """Return a (dim,) float32 vector for *text*."""
        ...

    def encode_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (N, dim) float32 matrix. One row per text."""
        ...
