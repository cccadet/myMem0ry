"""Runtime settings for myMem0ry."""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .domain.enums import SinkTarget


class Settings(BaseSettings):
    """Configuration loaded from environment variables or a .env file."""

    mem0_backend: SinkTarget = SinkTarget.LOCAL
    mem0_api_key: Optional[str] = None
    mem0_host: str = "https://api.mem0.ai"
    mem0_org_id: Optional[str] = None
    mem0_project_id: Optional[str] = None
    mem0_local_config: Optional[Dict[str, Any]] = None
    qdrant_url: Optional[str] = None
    default_user_id: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="before")
    def _normalize_local_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        config = values.get("mem0_local_config")
        if isinstance(config, str):
            if not config.strip():
                values["mem0_local_config"] = None
        return values

    def local_memory_config(self) -> Optional[Dict[str, Any]]:
        """Return a MemoryConfig override for the local sink if one is defined."""
        if self.mem0_local_config:
            return self.mem0_local_config
        qdrant_config = self._build_qdrant_config()
        if not qdrant_config:
            return None
        return {"vector_store": {"provider": "qdrant", "config": qdrant_config}}

    def _build_qdrant_config(self) -> Optional[Dict[str, Any]]:
        """Parse the QDRANT_URL setting into a config supported by Mem0."""
        if not self.qdrant_url:
            return None
        cleaned = self.qdrant_url.strip()
        if not cleaned:
            return None

        parsed = urlparse(cleaned if "://" in cleaned else f"//{cleaned}")
        host, port = parsed.hostname, parsed.port

        if host and port:
            return {"host": host, "port": port}

        if parsed.path and parsed.path != "/":
            return {"path": parsed.path}

        return None
