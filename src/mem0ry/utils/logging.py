"""Structured JSON logging for pipeline and observability.

Plain-text for CLI user output, JSON for everything else.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for agent-parseable observability."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exc"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Return a logger that emits structured JSON to stderr.

    >>> import logging
    >>> log = configure_logging(logging.DEBUG)
    >>> isinstance(log, logging.Logger)
    True
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("mem0ry")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    return root
