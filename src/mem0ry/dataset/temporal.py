"""Temporal enrichment: inject date context into conversations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from ..parsers.base import ParsedConversation


def format_timestamp(ts: str | float | None) -> str | None:
    if ts is None:
        return None
    try:
        value = float(ts)
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        try:
            dt = datetime.fromisoformat(str(ts))
        except (ValueError, TypeError):
            return None
    return dt.strftime("%A, %B %d, %Y at %H:%M UTC")


def build_temporal_system_prompt(
    conversation: ParsedConversation,
    base_prompt: str,
) -> str:
    parts = [base_prompt.rstrip()]

    date_str = format_timestamp(conversation.create_time)
    if date_str:
        parts.append(f"\n\nThis conversation took place on {date_str}.")

    if conversation.title:
        safe = conversation.title.replace("\n", " ").strip()
        if safe:
            parts.append(f'The conversation title is: "{safe}".')

    return " ".join(parts)


def enrich_conversations(
    conversations: Sequence[ParsedConversation],
) -> list[ParsedConversation]:
    def _sort_key(conv: ParsedConversation) -> float:
        if conv.create_time is None:
            return 0.0
        try:
            return float(conv.create_time)
        except (ValueError, TypeError):
            return 0.0

    return sorted(conversations, key=_sort_key)
