from __future__ import annotations

import html
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ...db.store_memories.helpers import _query_terms_raw
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _icon, _layout, _memory_card
from .shared import PAGE_SIZE, SORTS, SOURCES


def _build_filters(
    lang: str,
    q: str,
    scope: str,
    mtype: str,
    source: str,
    tags_raw: str,
    date_from: str,
    date_to: str,
    pinned_only: bool,
    sort: str,
) -> str:
    """Render the search/filter form with grid layout, preserving current values."""

    def opts(options: list[tuple[str, str]], current: str, placeholder: str) -> str:
        out = f'<option value="">{placeholder}</option>'
        for v, label in options:
            sel = "selected" if current == v else ""
            out += f'<option value="{v}" {sel}>{label}</option>'
        return out

    scope_opts = opts(
        [(s, s) for s in ("global", "project", "context", "session")],
        scope,
        t("search.all_scopes", lang),
    )
    type_opts = opts(
        [(x, x) for x in ("fact", "decision", "pattern", "log")],
        mtype,
        t("search.all_types", lang),
    )
    source_opts = opts([(s, s) for s in SOURCES], source, t("search.all_sources", lang))
    sort_opts = "".join(
        f'<option value="{s}" {"selected" if sort == s else ""}>{t("search.sort." + s, lang)}</option>'
        for s in SORTS
    )
    pinned_checked = "checked" if pinned_only else ""

    input_cls = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-primary-900"
    label_cls = "mb-1 block text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400"

    return f"""<form method="get" action="/search" class="reveal mb-6 grid gap-4 rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)] md:grid-cols-2 lg:grid-cols-4">
  <div class="md:col-span-2">
    <label for="f-q" class="{label_cls}">{t('search.label_query', lang)}</label>
    <div class="relative">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{_icon('search', 'text-base', 18)}</span>
      <input type="text" id="f-q" name="q" value="{html.escape(q)}" placeholder="{t('search.placeholder', lang)}" autofocus class="{input_cls} pl-9">
    </div>
  </div>
  <div>
    <label for="f-tags" class="{label_cls}">{t('search.label_tags', lang)}</label>
    <input type="text" id="f-tags" name="tags" value="{html.escape(tags_raw)}" placeholder="{t('search.tags_placeholder', lang)}" class="{input_cls}">
  </div>
  <div>
    <label for="f-scope" class="{label_cls}">{t('search.label_scope', lang)}</label>
    <select id="f-scope" name="scope" class="{input_cls}">{scope_opts}</select>
  </div>
  <div>
    <label for="f-type" class="{label_cls}">{t('search.label_type', lang)}</label>
    <select id="f-type" name="type" class="{input_cls}">{type_opts}</select>
  </div>
  <div>
    <label for="f-source" class="{label_cls}">{t('search.label_source', lang)}</label>
    <select id="f-source" name="source" class="{input_cls}">{source_opts}</select>
  </div>
  <div>
    <label for="f-from" class="{label_cls}">{t('search.date_from', lang)}</label>
    <input type="date" id="f-from" name="from" value="{html.escape(date_from)}" class="{input_cls}">
  </div>
  <div>
    <label for="f-to" class="{label_cls}">{t('search.date_to', lang)}</label>
    <input type="date" id="f-to" name="to" value="{html.escape(date_to)}" class="{input_cls}">
  </div>
  <div>
    <label for="f-sort" class="{label_cls}">{t('search.sort', lang)}</label>
    <select id="f-sort" name="sort" class="{input_cls}">{sort_opts}</select>
  </div>
  <div class="flex items-end gap-3 md:col-span-2 lg:col-span-4">
    <label class="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
      <input type="checkbox" name="pinned" value="1" {pinned_checked} class="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-800">
      {t('search.only_pinned', lang)}
    </label>
    <button type="submit" class="ml-auto inline-flex items-center gap-1 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700">{_icon('search')}{t('search.button', lang)}</button>
  </div>
</form>"""


def _parse_search_params(qp: Any) -> dict[str, Any]:
    """Extract and normalize query params for the search page."""
    sort = qp.get("sort", "recent")
    if sort not in SORTS:
        sort = "recent"
    try:
        page = max(1, int(qp.get("page", "1")))
    except ValueError:
        page = 1
    tags_raw = qp.get("tags", "")
    tags = [tg.strip() for tg in tags_raw.replace(",", " ").split() if tg.strip()]
    return {
        "q": qp.get("q", ""),
        "scope": qp.get("scope", ""),
        "mtype": qp.get("type", ""),
        "source": qp.get("source", ""),
        "tags_raw": tags_raw,
        "tags": tags,
        "date_from": qp.get("from", ""),
        "date_to": qp.get("to", ""),
        "pinned_only": qp.get("pinned", "") == "1",
        "sort": sort,
        "page": page,
        "offset": (page - 1) * PAGE_SIZE,
    }


def _render_results(
    rows: list[dict[str, Any]],
    terms: list[str],
    lang: str,
) -> str:
    if not rows:
        return f'<div class="reveal rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">{t("common.no_results", lang)}</div>'
    return f'<div class="reveal mb-3 text-sm text-slate-500 dark:text-slate-400">{len(rows)} {t("common.results", lang)}</div>' + "".join(
        _memory_card(r, lang, terms) for r in rows
    )


def _render_pager(
    page: int,
    has_next: bool,
    qp: Any,
    lang: str,
) -> str:
    if page <= 1 and not has_next:
        return ""
    base_params = {k: v for k, v in qp.items() if k != "page"}

    def page_link(p: int, label: str) -> str:
        params = dict(base_params)
        params["page"] = str(p)
        qs = "&".join(f"{html.escape(k)}={html.escape(str(v))}" for k, v in params.items())
        return f'<a href="/search?{qs}" class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">{label}</a>'

    parts = []
    if page > 1:
        parts.append(page_link(page - 1, _icon("arrow_back", "text-base", 16) + t("search.prev", lang)))
    parts.append(f'<span class="inline-flex h-9 items-center px-3 text-sm font-medium text-slate-500 dark:text-slate-400">{page}</span>')
    if has_next:
        parts.append(page_link(page + 1, t("search.next", lang) + _icon("arrow_forward", "text-base", 16)))
    return f'<div class="mt-6 flex items-center justify-center gap-3">{"".join(parts)}</div>'


def search_page(request: Request) -> HTMLResponse:
    from ...db.store import search_memories

    lang = get_lang(request)
    theme = get_theme(request)
    p = _parse_search_params(request.query_params)

    db = _db_path()
    results_html = ""
    pager_html = ""
    if db.exists():
        conn = get_connection(db)
        init_schema(conn)
        conn.close()
        rows = search_memories(
            db,
            query=p["q"] or None,
            scope=p["scope"] or None,
            memory_type=p["mtype"] or None,
            tags=p["tags"] or None,
            source=p["source"] or None,
            pinned_only=p["pinned_only"],
            date_from=p["date_from"] or None,
            date_to=p["date_to"] or None,
            order_by=p["sort"],
            top_k=PAGE_SIZE + 1,
            offset=p["offset"],
        )
        has_next = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        terms = _query_terms_raw(p["q"])
        results_html = _render_results(rows, terms, lang)
        pager_html = _render_pager(p["page"], has_next, request.query_params, lang)

    filters = _build_filters(
        lang,
        p["q"],
        p["scope"],
        p["mtype"],
        p["source"],
        p["tags_raw"],
        p["date_from"],
        p["date_to"],
        p["pinned_only"],
        p["sort"],
    )
    body = f"{filters}{results_html}{pager_html}"

    return HTMLResponse(_layout(t("nav.search", lang), body, "search", lang, theme))
