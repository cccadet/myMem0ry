"""Configuration for the myMem0ry KV cache pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass
class MemoryConfig:
    extraction_backend: str = os.environ.get("EXTRACTION_BACKEND", "ollama")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen3.5:0.8b")
    ollama_base_url: str = os.environ.get(
        "OLLAMA_BASE_URL", "http://localhost:11434/v1"
    )
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "")
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano")
    kvcache_model: str = os.environ.get("KVCACHE_MODEL", "Qwen/Qwen3.5-0.8B")
    kvcache_path: str = os.environ.get("KVCACHE_PATH", "memoria.kvcache")
    kvcache_meta_path: str = os.environ.get("KVCACHE_META_PATH", "memoria.meta.json")
    kvcache_max_tokens: int = int(os.environ.get("KVCACHE_MAX_TOKENS", "1024"))
    extraction_max_tokens: int = int(os.environ.get("EXTRACTION_MAX_TOKENS", "2048"))
    extraction_temperature: float = float(
        os.environ.get("EXTRACTION_TEMPERATURE", "0.3")
    )
    chat_max_new_tokens: int = int(os.environ.get("CHAT_MAX_NEW_TOKENS", "256"))
    system_prompt: str = (
        "You are a personal memory assistant with deep knowledge of the user's "
        "past conversations, preferences, projects, and personal history. "
        "Answer questions about the user based on everything you remember from "
        "those conversations. Be specific and reference details when possible."
    )
    default_user_id: str = os.environ.get("DEFAULT_USER_ID", "me")
    conversations_dir: str = os.environ.get("CONVERSATIONS_DIR", "data/conversations")
    search_top_k: int = int(os.environ.get("SEARCH_TOP_K", "3"))
