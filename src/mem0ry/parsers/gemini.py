"""Parser for Gemini (Google Takeout) export JSON files."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

from .base import BaseParser, ParsedConversation, ParsedMessage


class _HTMLStripper(HTMLParser):
    """Strip HTML tags and decode entities to plain text."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        from html import unescape

        self._parts.append(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        from html import unescape

        self._parts.append(unescape(f"&#{name};"))

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


_PROMPTED_PREFIX = "Prompted "


def _parse_entry(raw: dict, index: int, source_file: str) -> ParsedConversation | None:
    title = raw.get("title", "")
    time_str = raw.get("time")
    html_items = raw.get("safeHtmlItem", [])

    user_content = ""
    if title.startswith(_PROMPTED_PREFIX):
        user_content = title[len(_PROMPTED_PREFIX) :].strip()

    assistant_parts: list[str] = []
    for item in html_items:
        html = item.get("html", "")
        text = _strip_html(html)
        if text:
            assistant_parts.append(text)

    if not user_content and not assistant_parts:
        return None

    messages: list[ParsedMessage] = []
    if user_content:
        messages.append(
            ParsedMessage(role="user", content=user_content, created_at=time_str)
        )
    if assistant_parts:
        messages.append(
            ParsedMessage(
                role="assistant",
                content="\n\n".join(assistant_parts),
                created_at=time_str,
            )
        )

    return ParsedConversation(
        conversation_id=f"gemini-{index}",
        title=title or None,
        create_time=time_str,
        messages=messages,
        metadata={"source_file": source_file},
    )


class GeminiParser(BaseParser):
    """Normalize Gemini Takeout exports into conversations."""

    def parse(self, path: Path) -> list[ParsedConversation]:
        with open(path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)

        entries = payload if isinstance(payload, list) else []
        conversations: list[ParsedConversation] = []

        for i, raw in enumerate(entries):
            conv = _parse_entry(raw, i, path.name)
            if conv is not None:
                conversations.append(conv)

        return conversations
