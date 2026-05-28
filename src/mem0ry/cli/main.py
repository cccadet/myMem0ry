"""Typer CLI for myMem0ry — personal memory search system."""

from __future__ import annotations

from mem0ry.cli._app import app  # noqa: F401

import mem0ry.cli.conversation  # noqa: F401
import mem0ry.cli.migration  # noqa: F401
import mem0ry.cli.diagnostics  # noqa: F401
import mem0ry.cli.memory  # noqa: F401
import mem0ry.cli.retention  # noqa: F401
import mem0ry.cli.server  # noqa: F401
import mem0ry.cli.handoff  # noqa: F401
import mem0ry.cli.backup  # noqa: F401

from mem0ry.cli.conversation import _get_expander, _build_vector_index  # noqa: F401
from ..conversations.search_bm25 import build_bm25_index  # noqa: F401
from ..conversations.search_fts import build_fts_index  # noqa: F401
from ..config import MemoryConfig  # noqa: F401
