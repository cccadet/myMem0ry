from __future__ import annotations

import html
from typing import Any

from ..i18n import t

# Sources users can filter by (stable display order).
SOURCES = ("claude-code", "opencode", "codex", "manual", "import", "hook")
# Selectable sort keys (must match store_memories.search._ORDER_BY_M).
SORTS = ("recent", "oldest", "salience", "access", "title")
PAGE_SIZE = 25


def no_db_html(lang: str) -> str:
    return f'<div class="card"><p>{t("common.no_db", lang)}</p></div>'


def ago_label(iso: str | None, lang: str) -> str:
    """Humanize an ISO timestamp into a short relative label (best-effort)."""
    if not iso:
        return ""
    from datetime import datetime

    raw = str(iso).replace("Z", "").split(".")[0]
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return raw[:16]
    delta = datetime.now() - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return t("time.just_now", lang)
    mins = secs // 60
    if mins < 60:
        return t("time.min_ago", lang, n=mins)
    hours = mins // 60
    if hours < 24:
        return t("time.hour_ago", lang, n=hours)
    days = hours // 24
    return t("time.day_ago", lang, n=days)


def comp_bar(rows: list[Any], kind: str, lang: str) -> str:
    """Render a composition bar + legend for a scope/type breakdown.

    ``kind`` is ``"scope"`` or ``"type"`` and drives both the color class
    (``c-<key>``) and the filter link (``/search?<kind>=<key>``).
    """
    items = [(str(r[0]), r["cnt"]) for r in rows if r[0]]
    total = sum(c for _, c in items) or 1
    bar = "".join(
        f'<i class="c-{key}" style="width:{cnt / total * 100:.4g}%"></i>' for key, cnt in items
    )
    legend = "".join(
        f'<a href="/search?{kind}={html.escape(key)}"><span>'
        f'<span class="sw c-{key}"></span>{html.escape(key)} <b>{cnt}</b></span></a>'
        for key, cnt in items
    )
    ttl = t("dash.scope" if kind == "scope" else "dash.type", lang)
    return (
        f'<div class="comp-block"><div class="ttl">{ttl}</div>'
        f'<div class="bar">{bar}</div><div class="legend">{legend}</div></div>'
    )


def delete_form(target_id: str, target_type: str, confirm: str, label: str) -> str:
    action = f"/{target_type}/{target_id}/delete"
    return (
        f'<form method="post" action="{action}" '
        f'style="display:inline" '
        f'onsubmit="return confirm(\'{confirm}\')">'
        f'<button type="submit" class="btn btn-danger">{label}</button></form>'
    )


def target_link(row: dict[str, Any]) -> str:
    from ..templates import _esc

    ttype = row.get("target_type", "")
    tid = row.get("target_id", "")
    if ttype == "observation":
        href = f"/observation/{tid}"
    elif ttype == "handoff":
        href = f"/handoff/{tid}"
    else:
        href = f"/memory/{tid}"
    return f'<a href="{href}">{_esc(tid)}</a>'
