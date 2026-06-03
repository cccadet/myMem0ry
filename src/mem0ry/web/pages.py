from __future__ import annotations

import html
import json
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..db.connection import get_connection
from ..db.schema import init_schema
from ..db.store_memories import _query_terms
from .i18n import get_lang, get_theme, t
from .templates import (
    _TITLE_AUDIT,
    _db_path,
    _esc,
    _layout,
    _memory_card,
    _parse_tags,
    _salience_bar,
    _tag,
)

# Sources users can filter by (stable display order).
_SOURCES = ("claude-code", "opencode", "codex", "manual", "import", "hook")
# Selectable sort keys (must match store_memories._ORDER_BY).
_SORTS = ("recent", "oldest", "salience", "access", "title")
_PAGE_SIZE = 25


def _no_db(lang: str) -> str:
    return f'<div class="card"><p>{t("common.no_db", lang)}</p></div>'


def _ago(iso: str | None, lang: str) -> str:
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


def _comp_bar(rows: list[Any], kind: str, lang: str) -> str:
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


def _delete_form(target_id: str, target_type: str, confirm: str, label: str) -> str:
    action = f"/{target_type}/{target_id}/delete"
    return (
        f'<form method="post" action="{action}" '
        f'style="display:inline" '
        f'onsubmit="return confirm(\'{confirm}\')">'
        f'<button type="submit" class="btn btn-danger">{label}</button></form>'
    )


def dashboard(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    body_parts: list[str] = []

    if not db.exists():
        body_parts.append(f'<div class="card"><p>{t("common.no_db_hint", lang)}</p></div>')
        return HTMLResponse(_layout("Dashboard", "\n".join(body_parts), "dashboard", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    total = conn.execute("SELECT count(*) FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '')").fetchone()[0]
    projects = conn.execute(
        "SELECT project_id, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') "
        "GROUP BY project_id ORDER BY cnt DESC LIMIT 10"
    ).fetchall()

    by_scope = conn.execute(
        "SELECT scope, count(*) as cnt FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') GROUP BY scope"
    ).fetchall()
    by_type = conn.execute(
        "SELECT memory_type, count(*) as cnt FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') GROUP BY memory_type"
    ).fetchall()

    recent = conn.execute(
        "SELECT * FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    evolutions = conn.execute(
        "SELECT count(*) FROM memories WHERE superseded_by IS NOT NULL AND superseded_by != ''"
    ).fetchone()[0]

    handoffs_open = conn.execute(
        "SELECT count(*) FROM handoffs WHERE status = 'open'"
    ).fetchone()[0]

    open_ho = conn.execute(
        "SELECT id, project_id, summary, created_at FROM handoffs "
        "WHERE status='open' ORDER BY created_at DESC LIMIT 4"
    ).fetchall()

    version_row = conn.execute(
        "SELECT value FROM schema_meta WHERE key='version'"
    ).fetchone()
    conn.close()

    schema_ver = version_row["value"] if version_row else "?"

    # ── resume band (pick up where you left off) ──
    if open_ho:
        ho_cards = "".join(
            f"""<a href="/handoff/{_esc(dict(r)['id'])}" class="ho">
        <div class="top">
          <span class="dotmark"></span>
          <span class="repo">{_esc(dict(r).get('project_id') or '—')}</span>
          <span class="ago">{_ago(dict(r).get('created_at'), lang)}</span>
        </div>
        <div class="sum">{_esc((dict(r).get('summary') or '')[:160])}</div>
      </a>"""
            for r in open_ho
        )
        body_parts.append(f"""<section class="resume reveal">
    <div class="resume-head">
      <span class="k">{t("dash.resume_k", lang)}</span>
      <h2>{t("dash.resume_title", lang)}</h2>
      <span class="pill">{handoffs_open} {t("ho.open", lang).lower()}</span>
      <span class="grow"></span>
      <a href="/handoffs?status=open" class="all">{t("dash.view_all_handoffs", lang)} →</a>
    </div>
    <div class="resume-list">{ho_cards}</div>
  </section>""")

    # ── stats ──
    body_parts.append(f"""<section class="stats reveal">
  <div class="stat"><div class="num">{total}</div><div class="lbl">{t("dash.memories", lang)}</div></div>
  <div class="stat"><div class="num">{len(projects)}</div><div class="lbl">{t("dash.projects", lang)}</div></div>
  <div class="stat is-accent"><a href="/handoffs?status=open"><div class="num">{handoffs_open}</div><div class="lbl">{t("dash.open_handoffs", lang)}</div></a></div>
  <div class="stat is-muted"><div class="num">{evolutions}</div><div class="lbl">{t("dash.evolved_facts", lang)}</div></div>
</section>
<div class="schema-chip">{t("dash.schema", lang)} <b>v{schema_ver}</b> · {t("dash.store_healthy", lang)}</div>""")

    # ── composition ──
    body_parts.append(f"""<section class="comp reveal">
  {_comp_bar(list(by_scope), "scope", lang)}
  {_comp_bar(list(by_type), "type", lang)}
</section>""")

    # ── recent memories ──
    cards_html = "".join(_memory_card(dict(r), lang) for r in recent)
    body_parts.append(f"""<div class="sec reveal">
    <h2>{t("dash.recent", lang)}</h2>
    <span class="grow"></span>
    <span class="minifilter">
      <a class="active">{t("dash.all", lang)}</a>
      <a href="/search?pinned=1">{t("dash.pinned", lang)}</a>
    </span>
  </div>
  <div id="mem-list">{cards_html}</div>""")

    return HTMLResponse(_layout("Dashboard", "\n".join(body_parts), "dashboard", lang, theme))


def projects_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(t("nav.projects", lang), _no_db(lang), "projects", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    mem_projects: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        "SELECT project_id, project_path, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') "
        "GROUP BY project_id"
    ).fetchall():
        r = dict(row)
        mem_projects[r["project_id"]] = {
            "project_id": r["project_id"],
            "project_path": r.get("project_path"),
            "mem_cnt": r["cnt"],
            "obs_cnt": 0,
        }

    for row in conn.execute(
        "SELECT project_id, count(*) as cnt FROM observations "
        "WHERE project_id IS NOT NULL GROUP BY project_id"
    ).fetchall():
        r = dict(row)
        pid = r["project_id"]
        if pid in mem_projects:
            mem_projects[pid]["obs_cnt"] = r["cnt"]
        else:
            mem_projects[pid] = {
                "project_id": pid,
                "project_path": None,
                "mem_cnt": 0,
                "obs_cnt": r["cnt"],
            }

    global_cnt = conn.execute(
        "SELECT count(*) FROM memories WHERE scope='global' AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '')"
    ).fetchone()[0]
    conn.close()

    sorted_projects = sorted(
        mem_projects.values(),
        key=lambda p: p["mem_cnt"] + p["obs_cnt"],
        reverse=True,
    )

    rows_html = "".join(
        f"""<tr>
  <td><a href="/project/{html.escape(p['project_id'])}">{_esc(p['project_id'])}</a></td>
  <td class="meta">{_esc(p.get('project_path'))}</td>
  <td>{p['mem_cnt']}</td>
  <td>{p['obs_cnt']}</td>
</tr>"""
        for p in sorted_projects
    )

    body = f"""<h2>{t("proj.global", lang)}</h2>
<div class="card"><a href="/project/global">{t("proj.global_count", lang, n=global_cnt)}</a></div>
<h2>{t("proj.projects", lang)}</h2>
<table><tr><th>{t("proj.col_id", lang)}</th><th>{t("proj.col_path", lang)}</th><th>{t("proj.col_mem", lang)}</th><th>{t("proj.col_obs", lang)}</th></tr>
{rows_html}</table>"""

    return HTMLResponse(_layout(t("nav.projects", lang), body, "projects", lang, theme))


def project_detail(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    pid = request.path_params["project_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Project", _no_db(lang), "projects", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    if pid == "global":
        rows = conn.execute(
            "SELECT * FROM memories WHERE scope='global' AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE project_id=? AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') ORDER BY created_at DESC LIMIT 100",
            (pid,),
        ).fetchall()

    by_scope = conn.execute(
        "SELECT scope, count(*) as cnt FROM memories WHERE project_id=? AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') GROUP BY scope",
        (pid,),
    ).fetchall() if pid != "global" else []

    conn.close()

    scope_html = " ".join(
        _tag(r["scope"], f'{r["scope"]} ({r["cnt"]})') for r in by_scope
    )

    cards_html = "".join(_memory_card(dict(r), lang) for r in rows)

    export_btn = f'<form method="post" action="/memories/export" style="margin-bottom:1rem;display:inline"><input type="hidden" name="project_id" value="{html.escape(pid)}"><button type="submit" class="btn btn-export">{t("proj.export", lang)}</button></form>'

    body = f"""<h2>{_esc(pid)}</h2>
<div>{scope_html}</div>
{export_btn}
<h2>{t("proj.memories_n", lang, n=len(rows))}</h2>
{cards_html if cards_html else f'<div class="card meta">{t("proj.no_memories", lang)}</div>'}"""

    return HTMLResponse(_layout(f"Project: {pid}", body, "projects", lang, theme))


def memory_detail(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    mid = request.path_params["memory_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Memory", _no_db(lang), "dashboard", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()

    if not row:
        conn.close()
        return HTMLResponse(_layout("Memory", f'<div class="card"><p>{t("mem.not_found", lang, id=mid)}</p></div>', "dashboard", lang, theme))

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
  <div style="margin-top:.5rem;display:flex;gap:.5rem;flex-wrap:wrap">{edit_btn} {pin_btn} {_delete_form(mid, 'memory', t("common.confirm_delete", lang), t("common.delete", lang))}</div>
</div>
<h3>{t("mem.content", lang)}</h3>
<pre>{content}</pre>"""

    return HTMLResponse(_layout(f"Memory: {m.get('title', mid)}", body, "dashboard", lang, theme))


def memory_edit_form(request: Request) -> HTMLResponse:
    from ..db.store import get_memory_by_id

    lang = get_lang(request)
    theme = get_theme(request)
    mid = request.path_params["memory_id"]
    m = get_memory_by_id(_db_path(), mid)
    if not m:
        return HTMLResponse(_layout("Memory", f'<div class="card"><p>{t("mem.not_found", lang, id=mid)}</p></div>', "dashboard", lang, theme))

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
    from ..db.store import update_memory

    mid = request.path_params["memory_id"]
    form = await request.form()
    title = str(form.get("title", ""))
    content = str(form.get("content", ""))
    tags_raw = str(form.get("tags", ""))
    tags = [tg.strip() for tg in tags_raw.replace(",", " ").split() if tg.strip()]

    update_memory(_db_path(), mid, title=title or None, content=content, tags=tags)
    return RedirectResponse(url=f"/memory/{mid}", status_code=303)


def pin_memory_page(request: Request) -> Any:
    from ..db.store import pin_memory

    mid = request.path_params["memory_id"]
    pin_memory(_db_path(), mid)
    return RedirectResponse(url=f"/memory/{mid}", status_code=303)


def unpin_memory_page(request: Request) -> Any:
    from ..db.store import unpin_memory

    mid = request.path_params["memory_id"]
    unpin_memory(_db_path(), mid)
    return RedirectResponse(url=f"/memory/{mid}", status_code=303)


def observation_detail(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    oid = request.path_params["observation_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Observation", _no_db(lang), "dashboard", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(_layout("Observation", f'<div class="card"><p>{t("obs.not_found", lang, id=oid)}</p></div>', "dashboard", lang, theme))

    o = dict(row)
    body_text = _esc(o.get("body") or "")
    oid = o["id"]

    body = f"""<div class="card">
  <h2>{_esc(o.get('title') or o['id'])}</h2>
  <div>{_tag(o.get('kind', 'other'), o.get('kind', 'other'))}</div>
  <div class="meta">
    {t("mem.created", lang)}: {(o.get('created_at') or '')[:19]} &middot;
    {t("obs.agent", lang)}: {_esc(o.get('agent'))} &middot;
    {t("obs.session", lang)}: {_esc(o.get('session_id'))}
  </div>
  <div class="meta">{t("obs.project", lang)}: {_esc(o.get('project_id'))} &middot; {t("obs.cwd", lang)}: {_esc(o.get('cwd'))}</div>
  <div style="margin-top:.5rem">{_delete_form(oid, 'observation', t("obs.confirm_delete", lang), t("common.delete", lang))}</div>
</div>
<h3>{t("obs.body", lang)}</h3>
<pre>{body_text if body_text else f'<em class="meta">{t("obs.empty", lang)}</em>'}</pre>"""

    return HTMLResponse(_layout(f"Observation: {o.get('title', oid)}", body, "dashboard", lang, theme))


def _build_filters(lang: str, q: str, scope: str, mtype: str,
                   source: str, tags_raw: str, date_from: str, date_to: str,
                   pinned_only: bool, sort: str) -> str:
    """Render the search/filter form, preserving current values."""
    def opts(options: list[tuple[str, str]], current: str, placeholder: str) -> str:
        out = f'<option value="">{placeholder}</option>'
        for v, label in options:
            sel = "selected" if current == v else ""
            out += f'<option value="{v}" {sel}>{label}</option>'
        return out

    scope_opts = opts([(s, s) for s in ("global", "project", "context", "session")], scope, t("search.all_scopes", lang))
    type_opts = opts([(x, x) for x in ("fact", "decision", "pattern", "log")], mtype, t("search.all_types", lang))
    source_opts = opts([(s, s) for s in _SOURCES], source, t("search.all_sources", lang))
    sort_opts = "".join(
        f'<option value="{s}" {"selected" if sort == s else ""}>{t("search.sort." + s, lang)}</option>'
        for s in _SORTS
    )
    pinned_checked = "checked" if pinned_only else ""

    return f"""<form method="get" action="/search" class="filters">
  <input type="text" name="q" value="{html.escape(q)}" placeholder="{t('search.placeholder', lang)}" autofocus>
  <input type="text" name="tags" value="{html.escape(tags_raw)}" placeholder="{t('search.tags_placeholder', lang)}">
  <select name="scope">{scope_opts}</select>
  <select name="type">{type_opts}</select>
  <select name="source">{source_opts}</select>
  <label class="meta">{t('search.date_from', lang)} <input type="date" name="from" value="{html.escape(date_from)}"></label>
  <label class="meta">{t('search.date_to', lang)} <input type="date" name="to" value="{html.escape(date_to)}"></label>
  <label class="meta"><input type="checkbox" name="pinned" value="1" {pinned_checked}> {t('search.only_pinned', lang)}</label>
  <label class="meta">{t('search.sort', lang)} <select name="sort">{sort_opts}</select></label>
  <button type="submit" class="btn">{t('search.button', lang)}</button>
</form>"""


def search_page(request: Request) -> HTMLResponse:
    from ..db.store import search_memories

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
    if sort not in _SORTS:
        sort = "recent"
    try:
        page = max(1, int(qp.get("page", "1")))
    except ValueError:
        page = 1

    tags = [tg.strip() for tg in tags_raw.replace(",", " ").split() if tg.strip()]
    offset = (page - 1) * _PAGE_SIZE

    db = _db_path()
    results_html = ""
    pager_html = ""
    if db.exists():
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
            top_k=_PAGE_SIZE + 1,
            offset=offset,
        )
        has_next = len(rows) > _PAGE_SIZE
        rows = rows[:_PAGE_SIZE]
        terms = _query_terms(q)

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


def _target_link(row: dict[str, Any]) -> str:
    ttype = row.get("target_type", "")
    tid = row.get("target_id", "")
    if ttype == "observation":
        href = f"/observation/{tid}"
    elif ttype == "handoff":
        href = f"/handoff/{tid}"
    else:
        href = f"/memory/{tid}"
    return f'<a href="{href}">{_esc(tid)}</a>'


def audit_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(_TITLE_AUDIT, _no_db(lang), "audit", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    conn.close()

    rows_html = "".join(
        f"""<tr>
  <td class="meta">{(dict(row).get('created_at') or '')[:19]}</td>
  <td>{_esc(dict(row)['action'])}</td>
  <td>{_esc(dict(row)['target_type'])}</td>
  <td>{_target_link(dict(row))}</td>
  <td class="meta">{_esc(dict(row).get('agent'))}</td>
  <td class="meta" style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{_esc(dict(row).get('details'))}</td>
</tr>"""
        for row in rows
    )

    body = f"""<h2>{t("audit.title", lang)} ({t("audit.entries", lang, n=len(rows))})</h2>
<table>
<tr><th>{t("audit.time", lang)}</th><th>{t("audit.action", lang)}</th><th>{t("audit.type", lang)}</th><th>{t("audit.target", lang)}</th><th>{t("audit.agent", lang)}</th><th>{t("audit.details", lang)}</th></tr>
{rows_html}
</table>"""

    return HTMLResponse(_layout(_TITLE_AUDIT, body, "audit", lang, theme))


def api_memories(request: Request) -> JSONResponse:
    from ..db.store import search_memories

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
    if sort not in _SORTS:
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


def delete_memory_page(request: Request) -> Any:
    from ..db.store import delete_memory

    mid = request.path_params["memory_id"]
    delete_memory(_db_path(), mid)
    return RedirectResponse(url="/", status_code=303)


def delete_observation_page(request: Request) -> Any:
    from ..db.store import delete_observation

    oid = request.path_params["observation_id"]
    delete_observation(_db_path(), oid)
    return RedirectResponse(url="/", status_code=303)


def trash_page(request: Request) -> HTMLResponse:
    from ..db.store import list_deleted_memories

    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(t("trash.title", lang), _no_db(lang), "trash", lang, theme))

    rows = list_deleted_memories(db)

    cards = []
    for m in rows:
        mid = m["id"]
        title = _esc(m.get("title") or mid)
        scope = m.get("scope", "global")
        mtype = m.get("memory_type", "log")
        deleted_at = (m.get("deleted_at") or "")[:19]
        grace = m.get("grace_until")
        grace_html = (grace[:10] if grace else t("trash.no_grace", lang))
        restore_form = (
            f'<form method="post" action="/memory/{mid}/restore" style="display:inline" '
            f'onsubmit="return confirm(\'{t("trash.confirm_restore", lang)}\')">'
            f'<button type="submit" class="btn">{t("common.restore", lang)}</button></form>'
        )
        cards.append(f"""<div class="card">
  <div><strong>{title}</strong> {_tag(scope, scope)} {_tag(mtype, mtype)}</div>
  <div class="meta">{t("trash.deleted_at", lang)}: {deleted_at} &middot; {t("trash.grace_until", lang)}: {grace_html}</div>
  <div style="margin-top:.4rem">{_esc((m.get('content') or '')[:200])}</div>
  <div style="margin-top:.5rem">{restore_form}</div>
</div>""")

    cards_html = "".join(cards) if cards else f'<div class="card meta">{t("trash.empty", lang)}</div>'

    body = f"""<h2>{t("trash.subtitle", lang, n=len(rows))}</h2>
<p class="meta" style="margin-bottom:1rem">{t("trash.hint", lang)}</p>
{cards_html}"""

    return HTMLResponse(_layout(t("trash.title", lang), body, "trash", lang, theme))


def restore_memory_page(request: Request) -> Any:
    from ..db.store import restore_memory

    mid = request.path_params["memory_id"]
    restore_memory(_db_path(), mid)
    return RedirectResponse(url="/trash", status_code=303)


def close_handoff_page(request: Request) -> Any:
    from ..db.store import close_handoff

    hid = request.path_params["handoff_id"]
    close_handoff(_db_path(), hid)
    return RedirectResponse(url=f"/handoff/{hid}", status_code=303)


def delete_handoff_page(request: Request) -> Any:
    from ..db.store import delete_handoff

    hid = request.path_params["handoff_id"]
    delete_handoff(_db_path(), hid)
    return RedirectResponse(url="/handoffs", status_code=303)


def handoffs_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(t("ho.title", lang), _no_db(lang), "handoffs", lang, theme))

    status_filter = request.query_params.get("status", "")

    conn = get_connection(db)
    init_schema(conn)

    if status_filter:
        rows = conn.execute(
            "SELECT * FROM handoffs WHERE status=? ORDER BY created_at DESC LIMIT 100",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM handoffs ORDER BY created_at DESC LIMIT 100"
        ).fetchall()

    counts = {
        r["status"]: r["cnt"]
        for r in conn.execute(
            "SELECT status, count(*) as cnt FROM handoffs GROUP BY status"
        ).fetchall()
    }
    conn.close()

    status_tabs = ""
    for s, label in [("", t("ho.all", lang)), ("open", t("ho.open", lang)), ("accepted", t("ho.accepted", lang)), ("expired", t("ho.expired", lang))]:
        active = "active" if status_filter == s else ""
        cnt = counts.get(s, "") if s else sum(counts.values())
        status_tabs += f'<a href="/handoffs{"?status="+s if s else ""}" class="{active}">{label} ({cnt})</a> '

    _STATUS_COLOR = {"open": "muted", "accepted": "project", "expired": "log"}

    rows_html = "".join(
        f"""<tr>
  <td><a href="/handoff/{_esc(dict(r)['id'])}">{_esc(dict(r)['id'])}</a></td>
  <td>{_tag(_STATUS_COLOR.get(dict(r)['status'], 'log'), dict(r)['status'])}</td>
  <td class="meta">{_esc(dict(r).get('from_agent'))}</td>
  <td class="meta">{_esc(dict(r).get('project_id'))}</td>
  <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{_esc((dict(r).get('summary') or '')[:120])}</td>
  <td class="meta">{(dict(r).get('created_at') or '')[:16]}</td>
  <td><form method="post" action="/handoff/{_esc(dict(r)['id'])}/delete" style="display:inline" onsubmit="return confirm('{t("ho.confirm_delete", lang)}')"><button type="submit" class="btn btn-danger" style="padding:.2rem .5rem;font-size:.8rem">{t("common.delete", lang)}</button></form></td>
</tr>"""
        for r in rows
    )

    body = f"""<h2>{t("ho.title", lang)}</h2>
<div style="margin-bottom:1rem">{status_tabs}</div>
<table>
<tr><th>{t("ho.col_id", lang)}</th><th>{t("ho.col_status", lang)}</th><th>{t("ho.col_from", lang)}</th><th>{t("ho.col_project", lang)}</th><th>{t("ho.col_summary", lang)}</th><th>{t("ho.col_created", lang)}</th><th></th></tr>
{rows_html if rows_html else f'<tr><td colspan="7" class="meta">{t("ho.none", lang)}</td></tr>'}
</table>"""

    return HTMLResponse(_layout(t("ho.title", lang), body, "handoffs", lang, theme))


def handoff_detail(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    hid = request.path_params["handoff_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Handoff", _no_db(lang), "handoffs", lang, theme))

    conn = get_connection(db)
    init_schema(conn)
    row = conn.execute("SELECT * FROM handoffs WHERE id=?", (hid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(_layout("Handoff", f'<div class="card"><p>{t("ho.not_found", lang, id=hid)}</p></div>', "handoffs", lang, theme))

    ho = dict(row)
    oq: list[str] = json.loads(ho.get("open_questions") or "[]")
    ns: list[str] = json.loads(ho.get("next_steps") or "[]")

    _STATUS_COLOR = {"open": "muted", "accepted": "project", "expired": "log"}
    status_tag = _tag(_STATUS_COLOR.get(ho["status"], "log"), ho["status"])

    oq_html = "".join(f"<li>{_esc(qi)}</li>" for qi in oq) if oq else f"<li class='meta'>{t('ho.none_item', lang)}</li>"
    ns_html = "".join(f"<li>{_esc(s)}</li>" for s in ns) if ns else f"<li class='meta'>{t('ho.none_item', lang)}</li>"

    actions: list[str] = []
    if ho["status"] == "open":
        actions.append(
            f'<form method="post" action="/handoff/{hid}/close" style="display:inline" '
            f'onsubmit="return confirm(\'{t("ho.confirm_close", lang)}\')">'
            f'<button type="submit" class="btn">{t("ho.close", lang)}</button></form>'
        )
    actions.append(
        f'<form method="post" action="/handoff/{hid}/delete" style="display:inline" '
        f'onsubmit="return confirm(\'{t("ho.confirm_delete", lang)}\')">'
        f'<button type="submit" class="btn btn-danger">{t("common.delete", lang)}</button></form>'
    )
    actions_html = " ".join(actions)

    body = f"""<div class="card">
  <h2>Handoff {_esc(hid)}</h2>
  <div>{status_tag}</div>
  <div class="meta" style="margin-top:.5rem">
    {t("ho.from", lang)}: {_esc(ho.get('from_agent'))} &middot;
    {t("ho.created", lang)}: {(ho.get('created_at') or '')[:19]} &middot;
    {t("ho.expires", lang)}: {(ho.get('expires_at') or '')[:10]}
  </div>
  <div class="meta">
    {t("ho.project", lang)}: {_esc(ho.get('project_id'))} &middot;
    {t("ho.path", lang)}: {_esc(ho.get('project_path'))} &middot;
    {t("ho.session", lang)}: {_esc(ho.get('session_id'))}
  </div>
  {f'<div class="meta">{t("ho.accepted_by", lang)}: {_esc(ho.get("accepted_by"))} @ {(ho.get("accepted_at") or "")[:19]}</div>' if ho.get("accepted_by") else ""}
  <div style="margin-top:.5rem;display:flex;gap:.5rem;flex-wrap:wrap">{actions_html}</div>
</div>
<h3>{t("ho.summary", lang)}</h3>
<pre>{_esc(ho.get('summary') or '')}</pre>
<h3>{t("ho.open_questions", lang)}</h3>
<ul style="padding-left:1.5rem">{oq_html}</ul>
<h3>{t("ho.next_steps", lang)}</h3>
<ul style="padding-left:1.5rem">{ns_html}</ul>"""

    return HTMLResponse(_layout(f"Handoff: {hid}", body, "handoffs", lang, theme))


async def batch_delete_memories(request: Request) -> Any:
    from ..db.store import delete_memories_batch

    form = await request.form()
    ids = [str(v) for v in form.getlist("ids")]
    if ids:
        delete_memories_batch(_db_path(), ids)
    return RedirectResponse(url="/", status_code=303)


async def export_memories_page(request: Request) -> Response:
    from ..db.store import export_memories, export_handoffs

    form = await request.form()
    ids = [str(v) for v in form.getlist("ids")]
    scope_val = form.get("scope", "")
    project_id_val = form.get("project_id", "")

    scope_str = str(scope_val) if scope_val else ""
    project_id_str = str(project_id_val) if project_id_val else ""

    filters: dict[str, Any] = {}
    if ids:
        filters["memory_ids"] = ids
    if scope_str:
        filters["scope"] = scope_str
    if project_id_str:
        filters["project_id"] = project_id_str

    data = export_memories(_db_path(), **filters)

    pid = project_id_str or None
    handoffs = export_handoffs(_db_path(), project_id=pid)
    if handoffs:
        data["handoffs"] = handoffs

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    filename = "mem0ry-export.json"
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def import_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    msg = request.query_params.get("msg", "")
    msg_html = f'<div class="card" style="border-color:var(--green)"><p>{html.escape(msg)}</p></div>' if msg else ""

    body = f"""<h2>{t("imp.title", lang)}</h2>
{msg_html}
<form method="post" action="/memories/import" enctype="multipart/form-data" style="margin:1rem 0">
  <div style="margin-bottom:.5rem">
    <label for="file" style="color:var(--text2)">{t("imp.select_file", lang)}</label><br>
    <input type="file" name="file" accept=".json" required style="margin-top:.3rem;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.5rem;border-radius:6px">
  </div>
  <div style="margin-bottom:.5rem">
    <label style="color:var(--text2)">{t("imp.override", lang)}</label><br>
    <input type="text" name="project_id_override" placeholder="e.g. https://github.com/org/repo" style="margin-top:.3rem">
  </div>
  <button type="submit" class="btn">{t("imp.button", lang)}</button>
</form>
<div class="card">
  <p class="meta">{t("imp.help", lang)}</p>
</div>"""

    return HTMLResponse(_layout(t("imp.title", lang), body, "import-page", lang, theme))


async def import_memories_page(request: Request) -> Any:
    from ..db.store import import_memories, import_handoffs

    lang = get_lang(request)
    form = await request.form()
    upload = form.get("file")
    pid_raw = form.get("project_id_override", "")
    project_id_override: str | None = str(pid_raw) if pid_raw else None

    if not upload or not hasattr(upload, "read"):
        return RedirectResponse(url=f"/import?msg={html.escape(t('imp.no_file', lang))}", status_code=303)

    content_bytes = await upload.read()
    try:
        data = json.loads(content_bytes)
    except json.JSONDecodeError as e:
        return RedirectResponse(url=f"/import?msg={html.escape(t('imp.invalid_json', lang, err=str(e)))}", status_code=303)

    mem_result = import_memories(_db_path(), data, project_id_override=project_id_override)
    ho_result = {"imported": 0, "skipped": 0}
    if data.get("handoffs"):
        ho_result = import_handoffs(
            _db_path(), data["handoffs"], project_id_override=project_id_override
        )

    msg = t(
        "imp.result",
        lang,
        mem=mem_result["imported"],
        ho=ho_result["imported"],
        mem_skip=mem_result["skipped"],
        ho_skip=ho_result["skipped"],
    )
    return RedirectResponse(url=f"/import?msg={html.escape(msg)}", status_code=303)
