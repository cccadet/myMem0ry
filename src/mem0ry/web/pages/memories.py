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
            _layout("Memory", f'<div class="card"><p>{t("mem.not_found", lang, id=mid)}</p></div>', "dashboard", lang, theme)
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
        superseded_info = f'<div style="margin-top:.3rem">{_tag("superseded", t("mem.superseded_by", lang))} <a href="/memory/{_esc(m["superseded_by"])}">{_esc(m["superseded_by"])}</a></div>'

    superseded_rows = ""
    if incoming:
        links = ", ".join(f'<a href="/memory/{_esc(r["id"])}">{_esc(r["title"] or r["id"])}</a>' for r in incoming)
        superseded_rows = f'<div style="margin-top:.3rem"><strong>{t("mem.supersedes", lang)}</strong> {links}</div>'

    # Pin / unpin toggle
    if m.get("pinned"):
        pin_btn = f'<form method="post" action="/memory/{mid}/unpin" style="display:inline"><button type="submit" class="btn">{t("common.unpin", lang)}</button></form>'
    else:
        pin_btn = f'<form method="post" action="/memory/{mid}/pin" style="display:inline"><button type="submit" class="btn">{t("common.pin", lang)}</button></form>'

    edit_btn = f'<a href="/memory/{mid}/edit" class="btn" style="text-decoration:none">{t("common.edit", lang)}</a>'

    body = f"""<div class="card">
  <h2>{_esc(m.get('title') or m['id'])}</h2>
  <div>{_tag(m['scope'], m['scope'])} {_tag(m.get('memory_type','log'), m.get('memory_type','log'))}
  {(f' <span class="meta pinned">{t("common.pinned", lang)}</span>' if m.get('pinned') else '')}</div>
  {superseded_info}{superseded_rows}
  <div class="meta">
    {t("mem.created", lang)}: {(m.get('created_at') or '')[:19]} &middot;
    {t("mem.updated", lang)}: {(m.get('updated_at') or t("mem.never", lang))[:19]} &middot;
    {t("mem.source", lang)}: {m.get('source','')} &middot;
    {t("mem.access", lang)}: {m.get('access_count',0)}x &middot;
    {t("mem.salience", lang)}: {m.get('salience',0):.3f} {_salience_bar(float(m.get('salience',0) or 0), lang)}
  </div>
  <div class="meta">{t("mem.project", lang)}: {_esc(m.get('project_id'))} &middot; {t("mem.context", lang)}: {_esc(m.get('context'))} &middot; {t("mem.session", lang)}: {_esc(m.get('session_id'))}</div>
  {f'<div style="margin-top:.4rem">{tags_html}</div>' if tags else ''}
  <div style="margin-top:.5rem;display:flex;gap:.5rem;flex-wrap:wrap">{edit_btn} {pin_btn} {delete_form(mid, 'memory', t("common.confirm_delete", lang), t("common.delete", lang))}</div>
</div>
<h3>{t("mem.content", lang)}</h3>
<pre>{content}</pre>"""

    return HTMLResponse(_layout(f"Memory: {m.get('title', mid)}", body, "dashboard", lang, theme))


def memory_edit_form(request: Request) -> HTMLResponse:
    from ...db.store import get_memory_by_id

    lang = get_lang(request)
    theme = get_theme(request)
    mid = request.path_params["memory_id"]
    m = get_memory_by_id(_db_path(), mid)
    if not m:
        return HTMLResponse(
            _layout("Memory", f'<div class="card"><p>{t("mem.not_found", lang, id=mid)}</p></div>', "dashboard", lang, theme)
        )

    tags = ", ".join(_parse_tags(m.get("tags")))

    body = f"""<h2>{t("edit.title", lang)}</h2>
<form method="post" action="/memory/{mid}/edit">
  <div style="margin-bottom:.6rem">
    <label style="color:var(--text2)">{t("edit.title_label", lang)}</label><br>
    <input type="text" name="title" value="{_esc(m.get('title'))}" style="max-width:600px">
  </div>
  <div style="margin-bottom:.6rem">
    <label style="color:var(--text2)">{t("edit.content_label", lang)}</label><br>
    <textarea name="content" rows="12">{_esc(m.get('content'))}</textarea>
  </div>
  <div style="margin-bottom:.6rem">
    <label style="color:var(--text2)">{t("edit.tags_label", lang)}</label><br>
    <input type="text" name="tags" value="{_esc(tags)}" style="max-width:600px">
  </div>
  <div style="display:flex;gap:.5rem">
    <button type="submit" class="btn">{t("common.save", lang)}</button>
    <a href="/memory/{mid}" class="btn" style="background:var(--border);color:var(--text);text-decoration:none">{t("common.cancel", lang)}</a>
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
