from __future__ import annotations


class ParseError(ValueError):
    """Raised when a provider export cannot be parsed."""


class DuplicateError(ValueError):
    """Raised when an import contains data that already exists."""


class SinkError(RuntimeError):
    """Raised when a sink fails to store a conversation."""
