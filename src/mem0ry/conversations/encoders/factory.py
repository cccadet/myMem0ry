"""Factory for creating text encoders based on configuration."""

from __future__ import annotations

import logging

from ...config import MemoryConfig
from .base import TextEncoder
from .nomic_onnx import NomicOnnxEncoder
from .spacy import SpacyEncoder

logger = logging.getLogger(__name__)

VALID_ENCODER_BACKENDS = {"spacy", "nomic"}


def get_encoder(config: MemoryConfig | None = None) -> TextEncoder:
    """Return a ``TextEncoder`` instance configured for vector search.

    The backend is selected by ``MemoryConfig.vector_encoder_model`` (env
    ``VECTOR_ENCODER_MODEL``). Defaults to ``spacy`` to preserve existing
    behavior.

    Usage::

        encoder = get_encoder()
        print(encoder.dim)
    """
    cfg = config or MemoryConfig()
    backend = cfg.vector_encoder_model.lower().strip()

    if backend == "spacy":
        return SpacyEncoder(model_name=cfg.spacy_model)

    if backend == "nomic":
        return NomicOnnxEncoder()

    raise ValueError(
        f"Unknown vector encoder backend: '{cfg.vector_encoder_model}'. "
        f"Use one of: {', '.join(sorted(VALID_ENCODER_BACKENDS))}."
    )
