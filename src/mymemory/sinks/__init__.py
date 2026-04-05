"""Top-level helpers for working with mem0 sinks."""
from __future__ import annotations

from typing import Optional

from ..config import Settings
from ..domain.enums import SinkTarget
from .base import BaseSink
from .mem0_cloud import Mem0CloudSink
from .mem0_local import Mem0LocalSink

__all__ = ["BaseSink", "Mem0LocalSink", "Mem0CloudSink", "build_sink"]


def build_sink(settings: Optional[Settings] = None) -> BaseSink:
    """Create a mem0 sink according to the loaded settings."""
    settings = settings or Settings()
    if settings.mem0_backend == SinkTarget.CLOUD:
        return Mem0CloudSink(settings=settings)
    return Mem0LocalSink(settings=settings)
