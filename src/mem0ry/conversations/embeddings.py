"""Legacy re-export of the spaCy text encoder.

New code should import from ``mem0ry.conversations.encoders`` instead.
This module is kept for backward compatibility.
"""

from __future__ import annotations

from .encoders.spacy import SpacyEncoder

__all__ = ["SpacyEncoder"]
