"""Tests for config — MemoryConfig defaults."""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch

import pytest


def _reload_config() -> type:
    """Reload config module so environment overrides are re-read."""
    from mem0ry import config as config_module

    return importlib.reload(config_module).MemoryConfig


@patch.dict(os.environ, {"SPACY_MODEL": "en_core_web_lg"}, clear=False)
def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # The module-level load_dotenv may have already read .env; force a reload
    # with a controlled SPACY_MODEL so defaults are tested in isolation.
    MemoryConfig = _reload_config()
    config = MemoryConfig()
    assert config.expand_top_k == 10
    assert config.search_top_k == 3
    assert config.search_backend == "ripgrep"
    assert config.spacy_model == "en_core_web_lg"
    assert config.system_prompt is None


def test_custom_values() -> None:
    from mem0ry.config import MemoryConfig

    config = MemoryConfig(expand_top_k=5, search_backend="bm25")
    assert config.expand_top_k == 5
    assert config.search_backend == "bm25"
