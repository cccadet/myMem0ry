"""Configuration for the myMem0ry system."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[2]

load_dotenv(_project_root / ".env")


def _default_data_dir() -> Path:
    if _project_root.name == "site-packages" or _project_root.name == "mem0ry":
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(
                os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
            )
        return base / "mem0ry"
    return _project_root / "data"


_DATA_DIR = _default_data_dir()


def _resolve_file_path(raw: str, filename: str) -> str:
    p = Path(raw)
    if p.is_dir() or (not p.suffix and not p.exists()):
        return str(p / filename)
    return str(p)


@dataclass
class MemoryConfig:
    expand_top_k: int = int(os.environ.get("EXPAND_TOP_K", "10"))
    conversations_dir: str = os.environ.get(
        "CONVERSATIONS_DIR",
        str(_DATA_DIR / "conversations"),
    )
    search_top_k: int = int(os.environ.get("SEARCH_TOP_K", "3"))
    search_backend: str = os.environ.get("SEARCH_BACKEND", "ripgrep")
    spacy_model: str = os.environ.get("SPACY_MODEL", "en_core_web_lg")
    system_prompt: str | None = os.environ.get("SYSTEM_PROMPT", None)
    vector_db_path: str = _resolve_file_path(
        os.environ.get("VECTOR_DB_PATH", str(_DATA_DIR / "conversations" / ".vec.db")),
        ".vec.db",
    )
    embedding_dim: int = int(os.environ.get("EMBEDDING_DIM", "300"))
    rrf_k: int = int(os.environ.get("RRF_K", "60"))
    db_path: str = _resolve_file_path(
        os.environ.get("DB_PATH", str(_DATA_DIR / "memories.db")),
        "memories.db",
    )
    server_host: str = os.environ.get("MEM0RY_HOST", "127.0.0.1")
    server_port: int = int(os.environ.get("MEM0RY_PORT", "49374"))
    server_pid_file: str = os.environ.get(
        "MEM0RY_PID_FILE", str(_DATA_DIR / "server.pid")
    )
    auth_token: str | None = os.environ.get("MEM0RY_TOKEN", None)
    allowed_hosts: str = os.environ.get("MEM0RY_ALLOWED_HOSTS", "localhost,127.0.0.1")
    cors_origins: str = os.environ.get("MEM0RY_CORS_ORIGINS", "")
