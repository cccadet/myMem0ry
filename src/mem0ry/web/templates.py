from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .i18n import t

_TITLE_AUDIT = "Audit Log"
_NO_DB = '<div class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm"><p class="text-slate-600 dark:text-slate-400">No database found.</p></div>'


def _db_path() -> Path:
    from ..config import MemoryConfig

    return Path(MemoryConfig().db_path)


def _css() -> str:
    return """
:root{
  --md-sys-color-primary:#1a73e8;
  --md-sys-color-on-primary:#ffffff;
  --md-sys-color-primary-container:#d3e3fd;
  --md-sys-color-on-primary-container:#041e49;
  --md-sys-color-surface:#ffffff;
  --md-sys-color-surface-container-low:#f8f9fa;
  --md-sys-color-surface-container:#f1f3f4;
  --md-sys-color-surface-container-high:#e8eaed;
  --md-sys-color-on-surface:#1f1f1f;
  --md-sys-color-on-surface-variant:#444746;
  --md-sys-color-outline:#dadce0;
  --md-sys-color-outline-variant:#e8eaed;
  --md-sys-color-error:#b3261e;
  --md-sys-color-on-error:#ffffff;
  --md-sys-color-error-container:#f9dedc;
  --md-sys-color-on-error-container:#410e0b;
  --md-sys-color-secondary:#03a050;
  --md-sys-color-tertiary:#9334e6;
}
html[data-theme="dark"]{
  --md-sys-color-primary:#a8c7fa;
  --md-sys-color-on-primary:#062e6f;
  --md-sys-color-primary-container:#0842a0;
  --md-sys-color-on-primary-container:#d3e3fd;
  --md-sys-color-surface:#0b0f16;
  --md-sys-color-surface-container-low:#11161f;
  --md-sys-color-surface-container:#151b25;
  --md-sys-color-surface-container-high:#1b222e;
  --md-sys-color-on-surface:#e9eef5;
  --md-sys-color-on-surface-variant:#9aa4b3;
  --md-sys-color-outline:#262d39;
  --md-sys-color-outline-variant:#39414e;
  --md-sys-color-error:#f2b8b5;
  --md-sys-color-on-error:#601410;
  --md-sys-color-error-container:#8c1d18;
  --md-sys-color-on-error-container:#f9dedc;
}
.material-icons-outlined{font-family:'Material Icons Outlined';font-weight:normal;font-style:normal;display:inline-flex;line-height:1;text-transform:none;letter-spacing:normal;word-wrap:normal;white-space:nowrap;direction:ltr;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;-moz-osx-font-smoothing:grayscale;font-feature-settings:'liga'}
body{background:var(--md-sys-color-surface);color:var(--md-sys-color-on-surface)}
.reveal{opacity:0;transform:translateY(8px);animation:rise .45s cubic-bezier(.22,.61,.36,1) forwards}
@keyframes rise{to{opacity:1;transform:none}}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:var(--md-sys-color-outline-variant);border-radius:4px}
::-webkit-scrollbar-track{background:transparent}
"""


def _icon(name: str, class_name: str = "", size: int = 20) -> str:
    cls = f"material-icons-outlined {class_name}".strip()
    return f'<span class="{cls}" style="font-size:{size}px;line-height:1">{html.escape(name)}</span>'


def _batch_bar(lang: str = "pt") -> str:
    return f"""<div id="batch-bar" class="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 translate-y-full items-center gap-3 rounded-full border border-slate-300 bg-white px-4 py-2 shadow-lg transition-transform duration-300 dark:border-slate-600 dark:bg-slate-900">
  <span id="batch-count" class="font-mono font-bold text-primary-600 dark:text-primary-300">0</span>
  <span class="text-sm text-slate-600 dark:text-slate-400">{t("common.selected", lang)}</span>
  <form method="post" action="/memories/batch-delete" class="inline" id="batch-delete-form">
    <button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-semibold text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950" onclick="return confirm('{t('common.confirm_delete_sel', lang)}')">
      {_icon('delete', 'text-base')}{t("common.delete", lang)}
    </button>
  </form>
  <form method="post" action="/memories/export" class="inline" id="batch-export-form">
    <button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-green-200 px-3 py-1.5 text-sm font-semibold text-green-600 transition hover:bg-green-50 dark:border-green-900 dark:text-green-400 dark:hover:bg-green-950">
      {_icon('download', 'text-base')}{t("common.export", lang)}
    </button>
  </form>
  <button type="button" class="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700" onclick="toggleSelectAll()">
    {_icon('select_all', 'text-base')}{t("common.select_all", lang)}
  </button>
</div>"""


def _prefs_controls(lang: str, theme: str) -> str:
    theme_icon = "light_mode" if theme == "light" else "dark_mode"
    pt_active = "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300" if lang == "pt" else "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
    en_active = "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300" if lang == "en" else "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
    return f"""<div class="flex items-center gap-2">
  <span class="inline-flex overflow-hidden rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800" role="group" aria-label="{t('common.lang', lang)}">
    <a class="cursor-pointer px-2.5 py-1 text-xs font-medium transition {pt_active}" onclick="setLang('pt')">PT</a>
    <a class="cursor-pointer px-2.5 py-1 text-xs font-medium transition {en_active}" onclick="setLang('en')">EN</a>
  </span>
  <button class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700" onclick="toggleTheme()" aria-label="{t('common.theme', lang)}" title="{t('common.theme', lang)}">
    {_icon(theme_icon, 'text-lg', 18)}
  </button>
</div>"""


def _layout(
    title: str,
    body: str,
    nav_active: str = "dashboard",
    lang: str = "pt",
    theme: str = "dark",
) -> str:
    nav_items = [
        ("dashboard", "/", "dashboard", t("nav.dashboard", lang)),
        ("projects", "/projects", "folder", t("nav.projects", lang)),
        ("handoffs", "/handoffs", "swap_horiz", t("nav.handoffs", lang)),
        ("search", "/search", "search", t("nav.search", lang)),
        ("export", "/export", "download", t("nav.export", lang)),
        ("import-page", "/import", "upload", t("nav.import", lang)),
        ("trash", "/trash", "delete_outline", t("nav.trash", lang)),
        ("audit", "/audit", "history", t("nav.audit", lang)),
    ]
    nav_links = []
    for key, href, icon, label in nav_items:
        active = key == nav_active
        base = "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition"
        cls = f"{base} {'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300' if active else 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}"
        nav_links.append(f'<a href="{href}" class="{cls}">{_icon(icon)}{html.escape(label)}</a>')
    nav = "".join(nav_links)
    theme_attr = f' data-theme="{theme}"' if theme == "light" else ""
    return f"""<!DOCTYPE html>
<html lang="{lang}"{theme_attr} class="antialiased">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — myMem0ry</title>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Outlined" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {{
  darkMode: 'class',
  theme: {{
    extend: {{
      colors: {{
        primary: {{ 50: '#e8f0fe', 100: '#d2e3fc', 200: '#aecbfa', 300: '#8ab4f8', 400: '#669df6', 500: '#1a73e8', 600: '#1967d2', 700: '#185abc', 800: '#174ea6', 900: '#1557b0' }},
      }},
      fontFamily: {{
        sans: ['-apple-system','BlinkMacSystemFont','Segoe UI','Roboto','Helvetica','Arial','sans-serif'],
        mono: ['ui-monospace','SF Mono','JetBrains Mono','Cascadia Code','Menlo','Consolas','monospace'],
      }}
    }}
  }}
}}
</script>
<style>{_css()}</style>
</head>
<body class="min-h-screen bg-[var(--md-sys-color-surface)] text-[var(--md-sys-color-on-surface)]">
<header class="sticky top-0 z-40 border-b border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface)]/90 backdrop-blur">
  <div class="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-3 sm:px-6 lg:px-8">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <a href="/" class="flex items-baseline gap-1 font-mono text-xl font-bold tracking-tight text-[var(--md-sys-color-on-surface)]">
        myMem<span class="text-primary-600 dark:text-primary-300">0</span>ry
        <span class="ml-1 inline-flex h-2 w-2 rounded-full bg-green-500 shadow-[0_0_0_3px_rgba(34,197,94,0.25)]" title="server online"></span>
      </a>
      {_prefs_controls(lang, theme)}
    </div>
    <nav class="flex flex-wrap gap-1">{nav}</nav>
  </div>
</header>
<main class="mx-auto max-w-7xl px-4 py-6 pb-32 sm:px-6 lg:px-8">
{body}
</main>
{_batch_bar(lang)}
<script src="/static/js/lang.js"></script>
<script src="/static/js/theme.js"></script>
<script src="/static/js/batch.js"></script>
</body></html>"""


def _tag(cls: str, text: str, href: str | None = None) -> str:
    color_map = {
        "global": "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-900",
        "project": "bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-900",
        "context": "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900",
        "session": "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-900",
        "fact": "bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-950 dark:text-cyan-300 dark:border-cyan-900",
        "decision": "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-900",
        "pattern": "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900",
        "log": "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
        "superseded": "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-900",
        "muted": "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700",
        "green": "bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-900",
    }
    style = color_map.get(cls, color_map["log"])
    clickable = " cursor-pointer hover:opacity-80" if href else ""
    span = f'<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium font-mono whitespace-nowrap {style}{clickable}">{html.escape(text)}</span>'
    if href:
        return f'<a href="{html.escape(href)}">{span}</a>'
    return span


def _highlight(text: str, terms: list[str]) -> str:
    """HTML-escape ``text`` then wrap each query term in <mark> (case-insensitive)."""
    escaped = html.escape(text)
    for term in terms:
        if not term:
            continue
        pattern = re.compile(re.escape(html.escape(term)), re.IGNORECASE)
        escaped = pattern.sub(lambda mo: f'<mark class="rounded bg-amber-200 px-0.5 text-slate-900 dark:bg-amber-700 dark:text-white">{mo.group(0)}</mark>', escaped)
    return escaped


def _salience_bar(salience: float, lang: str) -> str:
    pct = max(0, min(100, round(salience * 100)))
    label = f"{t('mem.salience', lang)} {salience:.2f}"
    return f'<span class="inline-block h-1.5 w-12 align-middle rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden" title="{label}" aria-label="{label}"><i class="block h-full rounded-full bg-gradient-to-r from-primary-500 to-cyan-500" style="width:{pct}%"></i></span>'


def _esc(s: str | None) -> str:
    return html.escape(s or "")


def _parse_tags(raw: Any) -> list[str]:
    """Tags come back from SQLite as a JSON string; tolerate list or junk."""
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw:
        try:
            val = json.loads(raw)
            return [str(x) for x in val] if isinstance(val, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


_RAIL_TYPES = ("decision", "fact", "pattern", "log")


def _memory_card(
    m: dict[str, Any], lang: str = "pt", terms: list[str] | None = None
) -> str:
    title = _esc(m.get("title") or m["id"])
    scope = m.get("scope", "global")
    mtype = m.get("memory_type", "log")
    rail = mtype if mtype in _RAIL_TYPES else "log"
    pinned = m.get("pinned")
    superseded_by = m.get("superseded_by")
    created = (m.get("created_at") or "")[:10]
    raw_content = m.get("content", "") or ""
    snippet = raw_content[:200]
    content = _highlight(snippet, terms) if terms else _esc(snippet)
    if len(raw_content) > 200:
        content += "…"
    mid = m["id"]

    rail_color = {
        "decision": "bg-red-500",
        "fact": "bg-cyan-500",
        "pattern": "bg-emerald-500",
        "log": "bg-slate-400",
    }[rail]

    superseded_badge = ""
    if superseded_by:
        label = f'{t("mem.superseded_by", lang)} {superseded_by}'
        superseded_badge = f' <a href="/memory/{_esc(superseded_by)}">{_tag("superseded", label)}</a>'

    pin_chip = _icon("push_pin", "text-primary-600 dark:text-primary-300", 16) if pinned else ""

    ftags_html = "".join(
        f'<a class="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-mono text-slate-600 transition hover:bg-slate-200 hover:text-primary-600 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-primary-300" href="/search?tags={html.escape(tg)}">#{html.escape(tg)}</a>'
        for tg in _parse_tags(m.get("tags"))
    )
    ftags_block = f'<div class="mt-2 flex flex-wrap gap-1.5">{ftags_html}</div>' if ftags_html else ""

    access = m.get("access_count", 0) or 0
    salience = m.get("salience")
    sal_html = (
        f'<span class="inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">{t("mem.salience", lang)} {_salience_bar(float(salience), lang)}</span>'
        if salience is not None
        else ""
    )

    border_cls = "border-primary-300 dark:border-primary-700" if pinned else "border-[var(--md-sys-color-outline)]"

    return f"""<article class="reveal flex overflow-hidden rounded-xl border bg-[var(--md-sys-color-surface-container-low)] shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:bg-[var(--md-sys-color-surface-container)] dark:hover:border-slate-600 {border_cls}">
  <span class="w-1 self-stretch {rail_color}" aria-hidden="true"></span>
  <div class="flex-1 min-w-0 p-4">
    <div class="flex items-start gap-3">
      <input type="checkbox" class="mem-checkbox mt-1 h-4 w-4 cursor-pointer rounded border-slate-300 text-primary-600 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-800" value="{mid}" aria-label="Select memory {mid}">
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <a class="truncate text-base font-semibold text-[var(--md-sys-color-on-surface)] hover:text-primary-600 dark:hover:text-primary-300" href="/memory/{mid}">{title}</a>
          <span class="ml-auto flex flex-wrap items-center gap-1.5">{_tag(scope, scope)}{_tag(mtype, mtype)}{pin_chip}{superseded_badge}</span>
        </div>
        <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-mono text-slate-500 dark:text-slate-400">
          <span>{created}</span>
          <span class="h-1 w-1 rounded-full bg-slate-400"></span>
          <span>{_esc(m.get('source',''))}</span>
          <span class="h-1 w-1 rounded-full bg-slate-400"></span>
          <span class="inline-flex items-center gap-1">{_icon('replay', 'text-xs', 14)}{t("mem.accessed", lang)} <strong class="text-[var(--md-sys-color-on-surface)]">{access}{t("mem.times", lang)}</strong></span>
          {sal_html}
        </div>
        <div class="mt-2 line-clamp-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{content}</div>
        {ftags_block}
      </div>
    </div>
  </div>
</article>"""
