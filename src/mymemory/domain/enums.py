from __future__ import annotations

from enum import Enum


class SourceProvider(str, Enum):
    CHATGPT = "chatgpt"
    GEMINI = "gemini"
    CLAUDE = "claude"


class IngestionMode(str, Enum):
    MESSAGE = "message"
    CONVERSATION = "conversation"


class SinkTarget(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
