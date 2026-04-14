"""Export parsed conversations to individual .md files organized by date."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from ..parsers.openai import OpenAIParser


def _slugify(text: str) -> str:
    """Normalize text to a filesystem-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "untitled"


def _extract_date(create_time: str | None) -> str:
    """Extract YYYY-MM-DD from a create_time string, or return 'unknown'."""
    if not create_time:
        return "unknown"
    try:
        ts = float(create_time)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return "unknown"


def _format_conversation(conv) -> str:
    """Format a ParsedConversation as markdown."""
    lines = []

    title = conv.title or "Untitled"
    header = f"# {title}"
    lines.append(header)

    meta_parts = [f"id: {conv.conversation_id}"]
    if conv.create_time:
        meta_parts.append(f"date: {_extract_date(conv.create_time)}")
    lines.append(f"> {' | '.join(meta_parts)}")
    lines.append("")

    for msg in conv.messages:
        lines.append(f"[{msg.role}]: {msg.content}")
        lines.append("")

    return "\n".join(lines)


def split_conversations(
    source: Path,
    output: Path,
) -> dict:
    """Parse OpenAI exports and write each conversation to its own .md file.

    Returns a dict with stats: total, written, skipped.
    """
    parser = OpenAIParser()
    conversations = parser.parse_directory(source)

    stats = {"total": len(conversations), "written": 0, "skipped": 0}

    for conv in conversations:
        if not conv.messages:
            stats["skipped"] += 1
            continue

        date_dir = _extract_date(conv.create_time)
        slug = _slugify(conv.title or conv.conversation_id)

        dir_path = output / date_dir
        dir_path.mkdir(parents=True, exist_ok=True)

        filename = f"{slug}.md"
        file_path = dir_path / filename

        # Avoid overwriting: append suffix if file exists
        counter = 1
        while file_path.exists():
            file_path = dir_path / f"{slug}-{counter}.md"
            counter += 1

        content = _format_conversation(conv)
        file_path.write_text(content, encoding="utf-8")
        stats["written"] += 1

    return stats
