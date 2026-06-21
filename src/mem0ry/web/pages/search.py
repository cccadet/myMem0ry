from __future__ import annotations

import html

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ...db.store_memories.helpers import _query_terms_raw
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _layout, _memory_card
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

    return f"""<form method="get" action="/search" class="filters">
  <div class="filter-group">
    <label for="f-q">{t('search.label_query', lang)}</label>
    <input type="text" id="f-q" name="q" value="{html.escape(q)}" placeholder="{t('search.placeholder', lang)}" autofocus>
  </div>
  <div class="filter-group">
    <label for="f-tags">{t('search.label_tags', lang)}</label>
    <input type="text" id="f-tags" name="tags" value="{html.escape(tags_raw)}" placeholder="{t('search.tags_placeholder', lang)}">
  </div>
  <div class="filter-group">
    <label for="f-scope">{t('search.label_scope', lang)}</label>
    <select id="f-scope" name="scope">{scope_opts}</select>
  </div>
  <div class="filter-group">
    <label for="f-type">{t('search.label_type', lang)}</label>
    <select id="f-type" name="type">{type_opts}</select>
  </div>
  <div class="filter-group">
    <label for="f-source">{t('search.label_source', lang)}</label>
    <select id="f-source" name="source">{source_opts}</select>
  </div>
  <div class="filter-group">
    <label for="f-from">{t('search.date_from', lang)}</label>
    <input type="date" id="f-from" name="from" value="{html.escape(date_from)}">
  </div>
  <div class="filter-group">
    <label for="f-to">{t('search.date_to', lang)}</label>
    <input type="date" id="f-to" name="to" value="{html.escape(date_to)}">
  </div>
  <div class="filter-group">
    <label for="f-sort">{t('search.sort', lang)}</label>
    <select id="f-sort" name="sort">{sort_opts}</select>
  </div>
  <div class="filter-group filter-actions">
    <label class="meta" style="font-size:.85rem;text-transform:none;letter-spacing:0">
      <input type="checkbox" name="pinned" value="1" {pinned_checked}> {t('search.only_pinned', lang)}
    </label>
    <button type="submit" class="btn">{t('search.button', lang)}</button>
  </div>
</form>"""


def search_page(request: Request) -> HTMLResponse:
    from ...db.store import search_memories

    lang = get_lang(request)
    theme = get_theme(request)
    qp = request.query_params
    q = qp.get("q", "")
    scope = qp.get("scope", "")
    mtype = qp.get("type", "")
    source = qp.get("source", "")
    tags_raw = qp.get("tags", "")
    date_from = qp.get("from", "")
    date_to = qp.get("to", "")
    pinned_only = qp.get("pinned", "") == "1"
    sort = qp.get("sort", "recent")
    if sort not in SORTS:
        sort = "recent"
    try:
        page = max(1, int(qp.get("page", "1")))
    except ValueError:
        page = 1

    tags = [tg.strip() for tg in tags_raw.replace(",", " ").split() if tg.strip()]
    offset = (page - 1) * PAGE_SIZE

    db = _db_path()
    results_html = ""
    pager_html = ""
    if db.exists():
        conn = get_connection(db)
        init_schema(conn)
        conn.close()
        rows = search_memories(
            db,
            query=q or None,
            scope=scope or None,
            memory_type=mtype or None,
            tags=tags or None,
            source=source or None,
            pinned_only=pinned_only,
            date_from=date_from or None,
            date_to=date_to or None,
            order_by=sort,
            top_k=PAGE_SIZE + 1,
            offset=offset,
        )
        has_next = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        terms = _query_terms_raw(q)

        if rows:
            results_html = f'<div class="meta">{len(rows)} {t("common.results", lang)}</div>' + "".join(
                _memory_card(r, lang, terms) for r in rows
            )
        else:
            results_html = f'<div class="card meta">{t("common.no_results", lang)}</div>'

        # Pagination controls (preserve all current query params except page)
        base_params = {k: v for k, v in qp.items() if k != "page"}

        def page_link(p: int, label: str) -> str:
            params = dict(base_params)
            params["page"] = str(p)
            qs = "&".join(f"{html.escape(k)}={html.escape(str(v))}" for k, v in params.items())
            return f'<a href="/search?{qs}" class="btn" style="text-decoration:none">{label}</a>'

        parts = []
        if page > 1:
            parts.append(page_link(page - 1, t("search.prev", lang)))
        parts.append(f'<span class="meta">{page}</span>')
        if has_next:
            parts.append(page_link(page + 1, t("search.next", lang)))
        if page > 1 or has_next:
            pager_html = f'<div class="pager">{"".join(parts)}</div>'

    filters = _build_filters(lang, q, scope, mtype, source, tags_raw, date_from, date_to, pinned_only, sort)
    body = f"{filters}{results_html}{pager_html}"

    return HTMLResponse(_layout(t("nav.search", lang), body, "search", lang, theme))
