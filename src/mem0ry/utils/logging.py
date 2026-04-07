"""Small logging helpers for pipeline tasks."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger("mem0ry")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    return root
