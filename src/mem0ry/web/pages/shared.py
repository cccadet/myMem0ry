from __future__ import annotations

import html
from typing import Any

from ..i18n import t
from ..templates import _icon

# Sources users can filter by (stable display order).
SOURCES = ("claude-code", "opencode", "codex", "manual", "import", "hook")
# Selectable sort keys (must match store_memories.search._ORDER_BY_M).
SORTS = ("recent", "oldest", "salience", "access", "title")
PAGE_SIZE = 25


def no_db_html(lang: str) -> str:
    return (
        f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">'
        f'<p class="text-slate-600 dark:text-slate-400">{t("common.no_db", lang)}</p></div>'
    )


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
    and the filter link (``/search?<kind>=<key>``).
    """
    items = [(str(r[0]), r["cnt"]) for r in rows if r[0]]
    total = sum(c for _, c in items) or 1
    bar = "".join(
        f'<i class="block h-full {_color_class(key)}" style="width:{cnt / total * 100:.4g}%"></i>' for key, cnt in items
    )
    legend = "".join(
        f'<a href="/search?{kind}={html.escape(key)}" class="inline-flex items-center gap-1.5 text-sm text-slate-600 transition hover:text-primary-600 dark:text-slate-400 dark:hover:text-primary-300">'
        f'<span class="h-2.5 w-2.5 rounded-sm {_color_class(key)}"></span>{html.escape(key)} <span class="font-mono font-semibold text-slate-900 dark:text-slate-200">{cnt}</span></a>'
        for key, cnt in items
    )
    ttl = t("dash.scope" if kind == "scope" else "dash.type", lang)
    return (
        f'<div class="space-y-2"><div class="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{ttl}</div>'
        f'<div class="flex h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">{bar}</div>'
        f'<div class="flex flex-wrap gap-3">{legend}</div></div>'
    )


def _color_class(key: str) -> str:
    return {
        "global": "bg-blue-500",
        "project": "bg-green-500",
        "context": "bg-amber-500",
        "session": "bg-purple-500",
        "fact": "bg-cyan-500",
        "decision": "bg-red-500",
        "pattern": "bg-emerald-500",
        "log": "bg-slate-400",
    }.get(key, "bg-slate-400")


def delete_form(target_id: str, target_type: str, confirm: str, label: str) -> str:
    action = f"/{target_type}/{target_id}/delete"
    return (
        f'<form method="post" action="{action}" class="inline" onsubmit="return confirm(\'{confirm}\')">'
        f'<button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-semibold text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950">'
        f'{_icon("delete")}{label}</button></form>'
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
    return f'<a href="{href}" class="text-primary-600 hover:underline dark:text-primary-300">{_esc(tid)}</a>'
