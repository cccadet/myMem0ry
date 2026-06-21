"""Text encoders for vector search."""

from __future__ import annotations

from .base import TextEncoder
from .factory import VALID_ENCODER_BACKENDS, get_encoder
from .nomic_onnx import NomicOnnxEncoder
from .spacy import SpacyEncoder

__all__ = [
    "TextEncoder",
    "SpacyEncoder",
    "NomicOnnxEncoder",
    "get_encoder",
    "VALID_ENCODER_BACKENDS",
]
