"""Configuration for the myMem0ry system."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass
class MemoryConfig:
    model_name: str = os.environ.get("MODEL_NAME", "Qwen/Qwen3.5-0.8B")
    expand_top_k: int = int(os.environ.get("EXPAND_TOP_K", "10"))
    conversations_dir: str = os.environ.get("CONVERSATIONS_DIR", "data/conversations")
    search_top_k: int = int(os.environ.get("SEARCH_TOP_K", "3"))
    search_backend: str = os.environ.get("SEARCH_BACKEND", "ripgrep")
    expand_method: str = os.environ.get("EXPAND_METHOD", "ffn")
    spacy_model: str = os.environ.get("SPACY_MODEL", "pt_core_news_lg")
