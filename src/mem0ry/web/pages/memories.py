from __future__ import annotations

import html
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import (
    _db_path,
    _esc,
    _icon,
    _layout,
    _parse_tags,
    _salience_bar,
    _tag,
)
from .shared import SORTS, delete_form, no_db_html


def memory_detail(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    mid = request.path_params["memory_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Memory", no_db_html(lang), "dashboard", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()

    if not row:
        conn.close()
        return HTMLResponse(
            _layout("Memory", f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"><p class="text-slate-600 dark:text-slate-400">{t("mem.not_found", lang, id=mid)}</p></div>', "dashboard", lang, theme)
        )

    m = dict(row)

    incoming = conn.execute(
        "SELECT id, title FROM memories WHERE superseded_by = ? LIMIT 10",
        (mid,),
    ).fetchall()
    conn.close()

    tags = _parse_tags(m.get("tags"))
    tags_html = " ".join(_tag("log", tg, href=f"/search?tags={html.escape(tg)}") for tg in tags)

    content = _esc(m["content"])

    superseded_info = ""
    if m.get("superseded_by"):
        superseded_info = f'<div class="mt-2">{_tag("superseded", t("mem.superseded_by", lang))} <a href="/memory/{_esc(m["superseded_by"])}" class="text-primary-600 hover:underline dark:text-primary-300">{_esc(m["superseded_by"])}</a></div>'

    superseded_rows = ""
    if incoming:
        links = ", ".join(f'<a href="/memory/{_esc(r["id"])}" class="text-primary-600 hover:underline dark:text-primary-300">{_esc(r["title"] or r["id"])}</a>' for r in incoming)
        superseded_rows = f'<div class="mt-2"><strong class="text-slate-700 dark:text-slate-300">{t("mem.supersedes", lang)}</strong> {links}</div>'

    if m.get("pinned"):
        pin_btn = f'<form method="post" action="/memory/{mid}/unpin" class="inline"><button type="submit" class="inline-flex items-center gap-1 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700">{_icon("push_pin")}{t("common.unpin", lang)}</button></form>'
    else:
        pin_btn = f'<form method="post" action="/memory/{mid}/pin" class="inline"><button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">{_icon("push_pin")}{t("common.pin", lang)}</button></form>'

    edit_btn = f'<a href="/memory/{mid}/edit" class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">{_icon("edit")}{t("common.edit", lang)}</a>'

    body = f"""<div class="rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{_esc(m.get('title') or m['id'])}</h2>
  <div class="mb-3 flex flex-wrap items-center gap-2">{_tag(m['scope'], m['scope'])}{_tag(m.get('memory_type','log'), m.get('memory_type','log'))}
  {(f'<span class="inline-flex items-center gap-1 text-sm text-primary-600 dark:text-primary-300">{_icon("push_pin", "text-base", 16)}{t("common.pinned", lang)}</span>' if m.get('pinned') else '')}</div>
  {superseded_info}{superseded_rows}
  <div class="mt-3 space-y-1 text-sm text-slate-600 dark:text-slate-400">
    <div class="flex flex-wrap gap-x-4 gap-y-1">
      <span class="inline-flex items-center gap-1">{_icon("event", 'text-xs', 14)}<strong class="text-slate-800 dark:text-slate-200">{t("mem.created", lang)}:</strong> {(m.get('created_at') or '')[:19]}</span>
      <span class="inline-flex items-center gap-1">{_icon("update", 'text-xs', 14)}<strong class="text-slate-800 dark:text-slate-200">{t("mem.updated", lang)}:</strong> {(m.get('updated_at') or t("mem.never", lang))[:19]}</span>
      <span class="inline-flex items-center gap-1">{_icon("source", 'text-xs', 14)}<strong class="text-slate-800 dark:text-slate-200">{t("mem.source", lang)}:</strong> {m.get('source','')}</span>
      <span class="inline-flex items-center gap-1">{_icon("replay", 'text-xs', 14)}<strong class="text-slate-800 dark:text-slate-200">{t("mem.access", lang)}:</strong> {m.get('access_count',0)}x</span>
      <span class="inline-flex items-center gap-1">{t("mem.salience", lang)}: {m.get('salience',0):.3f} {_salience_bar(float(m.get('salience',0) or 0), lang)}</span>
    </div>
    <div class="flex flex-wrap gap-x-4 gap-y-1">
      <span><strong class="text-slate-800 dark:text-slate-200">{t("mem.project", lang)}:</strong> {_esc(m.get('project_id'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("mem.context", lang)}:</strong> {_esc(m.get('context'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("mem.session", lang)}:</strong> {_esc(m.get('session_id'))}</span>
    </div>
  </div>
  {f'<div class="mt-3 flex flex-wrap gap-1">{tags_html}</div>' if tags else ''}
  <div class="mt-4 flex flex-wrap gap-2">{edit_btn} {pin_btn} {delete_form(mid, 'memory', t("common.confirm_delete", lang), t("common.delete", lang))}</div>
</div>
<h3 class="mb-2 mt-6 text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("mem.content", lang)}</h3>
<pre class="overflow-x-auto whitespace-pre-wrap rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-4 text-sm leading-relaxed text-slate-800 shadow-sm dark:bg-[var(--md-sys-color-surface-container-high)] dark:text-slate-200">{content}</pre>"""

    return HTMLResponse(_layout(f"Memory: {m.get('title', mid)}", body, "dashboard", lang, theme))


def memory_edit_form(request: Request) -> HTMLResponse:
    from ...db.store import get_memory_by_id

    lang = get_lang(request)
    theme = get_theme(request)
    mid = request.path_params["memory_id"]
    m = get_memory_by_id(_db_path(), mid)
    if not m:
        return HTMLResponse(
            _layout("Memory", f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"><p class="text-slate-600 dark:text-slate-400">{t("mem.not_found", lang, id=mid)}</p></div>', "dashboard", lang, theme)
        )

    tags = ", ".join(_parse_tags(m.get("tags")))

    body = f"""<h2 class="mb-4 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("edit.title", lang)}</h2>
<form method="post" action="/memory/{mid}/edit" class="space-y-4">
  <div>
    <label class="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-400">{t("edit.title_label", lang)}</label>
    <input type="text" name="title" value="{_esc(m.get('title'))}" class="w-full max-w-2xl rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-primary-900">
  </div>
  <div>
    <label class="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-400">{t("edit.content_label", lang)}</label>
    <textarea name="content" rows="12" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-primary-900">{_esc(m.get('content'))}</textarea>
  </div>
  <div>
    <label class="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-400">{t("edit.tags_label", lang)}</label>
    <input type="text" name="tags" value="{_esc(tags)}" class="w-full max-w-2xl rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-primary-900">
  </div>
  <div class="flex flex-wrap gap-2">
    <button type="submit" class="inline-flex items-center gap-1 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700">{_icon("save")}{t("common.save", lang)}</button>
    <a href="/memory/{mid}" class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">{_icon("cancel")}{t("common.cancel", lang)}</a>
  </div>
</form>"""

    return HTMLResponse(_layout(t("edit.title", lang), body, "dashboard", lang, theme))


async def memory_edit_save(request: Request) -> Any:
    from ...db.store import update_memory

    mid = request.path_params["memory_id"]
    form = await request.form()
    title = str(form.get("title", ""))
    content = str(form.get("content", ""))
    tags_raw = str(form.get("tags", ""))
    tags = [tg.strip() for tg in tags_raw.replace(",", " ").split() if tg.strip()]

    update_memory(_db_path(), mid, title=title or None, content=content, tags=tags)
    return RedirectResponse(url=f"/memory/{mid}", status_code=303)


def pin_memory_page(request: Request) -> Any:
    from ...db.store import pin_memory

    mid = request.path_params["memory_id"]
    pin_memory(_db_path(), mid)
    return RedirectResponse(url=f"/memory/{mid}", status_code=303)


def unpin_memory_page(request: Request) -> Any:
    from ...db.store import unpin_memory

    mid = request.path_params["memory_id"]
    unpin_memory(_db_path(), mid)
    return RedirectResponse(url=f"/memory/{mid}", status_code=303)


def restore_memory_page(request: Request) -> Any:
    from ...db.store import restore_memory

    mid = request.path_params["memory_id"]
    restore_memory(_db_path(), mid)
    return RedirectResponse(url="/trash", status_code=303)


def delete_memory_page(request: Request) -> Any:
    from ...db.store import delete_memory

    mid = request.path_params["memory_id"]
    delete_memory(_db_path(), mid)
    return RedirectResponse(url="/", status_code=303)


def api_memories(request: Request) -> JSONResponse:
    from ...db.store import search_memories

    db = _db_path()
    if not db.exists():
        return JSONResponse([])

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
    limit = min(int(qp.get("limit", "50")), 200)
    tags = [tg.strip() for tg in tags_raw.replace(",", " ").split() if tg.strip()]

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
        top_k=limit,
    )
    return JSONResponse(rows)


async def batch_delete_memories(request: Request) -> Any:
    from ...db.store import delete_memories_batch

    form = await request.form()
    ids = [str(v) for v in form.getlist("ids")]
    if ids:
        delete_memories_batch(_db_path(), ids)
    return RedirectResponse(url="/", status_code=303)
