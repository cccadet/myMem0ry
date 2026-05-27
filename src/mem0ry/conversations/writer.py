"""Export parsed conversations to individual .md files organized by date."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..parsers.base import BaseParser
from ..parsers.claude import ClaudeCodeParser, ClaudeExportParser
from ..parsers.gemini import GeminiParser
from ..parsers.openai import OpenAIParser
from ..utils.filenames import sanitize_title

_PARSERS: dict[str, type[BaseParser]] = {
    "openai": OpenAIParser,
    "gemini": GeminiParser,
    "claude-code": ClaudeCodeParser,
    "claude-export": ClaudeExportParser,
}


def _extract_date(create_time: str | float | None) -> str:
    """Extract YYYY-MM-DD from a create_time string, or return 'unknown'."""
    if not create_time:
        return "unknown"
    if isinstance(create_time, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(create_time), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return "unknown"
    # Try ISO 8601 format first (Gemini: "2026-04-03T14:06:31.934Z")
    try:
        dt = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, OSError):
        pass
    # Try Unix timestamp (OpenAI: "1712345678.123")
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


def _detect_source_type(source: Path) -> str | None:
    """Auto-detect export type by inspecting files in the directory."""
    json_files = sorted(source.glob("*.json"))
    jsonl_files = sorted(source.glob("*.jsonl"))

    if jsonl_files:
        return "claude-code"

    if not json_files:
        return None

    import json

    with open(json_files[0], "r", encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    return _classify_payload(payload)


def _classify_payload(payload) -> str | None:
    """Identify export format from parsed JSON structure."""
    detectors = [
        (_is_gemini_list, "gemini"),
        (_is_openai_dict, "openai"),
        (_is_openai_list, "openai"),
        (_is_claude_export, "claude-export"),
    ]
    for detector_fn, source_type in detectors:
        if detector_fn(payload):
            return source_type
    return None


def _is_gemini_list(payload) -> bool:
    return isinstance(payload, list) and bool(payload) and "safeHtmlItem" in payload[0]


def _is_openai_dict(payload) -> bool:
    return isinstance(payload, dict) and (
        "conversations" in payload or "mapping" in payload
    )


def _is_openai_list(payload) -> bool:
    return isinstance(payload, list) and bool(payload) and "mapping" in payload[0]


def _is_claude_export(payload) -> bool:
    if isinstance(payload, list) and bool(payload):
        first = payload[0]
        return "chat_messages" in first or ("uuid" in first and "name" in first)
    if isinstance(payload, dict):
        convs = payload.get("conversations", [])
        return "chat_messages" in payload or (
            isinstance(convs, list) and bool(convs) and "chat_messages" in convs[0]
        )
    return False


def split_conversations(
    source: Path,
    output: Path,
    source_type: str | None = None,
) -> dict:
    """Parse exports and write each conversation to its own .md file.

    Auto-detects the export format (OpenAI or Gemini) unless source_type
    is explicitly provided ("openai" or "gemini").

    Returns a dict with stats: total, written, skipped.
    """
    detected = source_type or _detect_source_type(source)
    if not detected:
        raise ValueError(
            f"Could not detect export type in {source}. "
            f"Pass --type openai or --type gemini explicitly."
        )

    parser_cls = _PARSERS.get(detected)
    if not parser_cls:
        raise ValueError(f"Unknown source type: {detected}")

    parser = parser_cls()
    conversations = parser.parse_directory(source)

    stats = {"total": len(conversations), "written": 0, "skipped": 0}

    for conv in conversations:
        if not conv.messages:
            stats["skipped"] += 1
            continue

        date_dir = _extract_date(conv.create_time)
        safe_title = sanitize_title(conv.title or conv.conversation_id)

        dir_path = output / date_dir
        dir_path.mkdir(parents=True, exist_ok=True)

        filename = f"{safe_title}.md"
        file_path = dir_path / filename

        # Avoid overwriting: append suffix if file exists
        counter = 1
        while file_path.exists():
            file_path = dir_path / f"{safe_title}-{counter}.md"
            counter += 1

        content = _format_conversation(conv)
        file_path.write_text(content, encoding="utf-8")
        stats["written"] += 1

    return stats
