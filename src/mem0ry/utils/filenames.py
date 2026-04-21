"""Filename sanitization shared across conversation writers and MCP server."""

from __future__ import annotations

import re

_UNSAFE_FS_CHARS = re.compile(r'[/\\:*?"<>|\n\r]')


def sanitize_title(text: str) -> str:
    """Strip characters illegal in filenames, keep unicode intact.

    >>> sanitize_title("hello/world")
    'helloworld'
    >>> sanitize_title("  ")
    'untitled'
    """
    text = text.strip().replace("\n", " ")
    text = _UNSAFE_FS_CHARS.sub("", text)
    return text[:120] or "untitled"
