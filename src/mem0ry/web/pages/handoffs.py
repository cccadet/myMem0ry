from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _layout, _tag
from .shared import no_db_html


def close_handoff_page(request: Request) -> Any:
    from ...db.store import close_handoff

    hid = request.path_params["handoff_id"]
    close_handoff(_db_path(), hid)
    return RedirectResponse(url=f"/handoff/{hid}", status_code=303)


def delete_handoff_page(request: Request) -> Any:
    from ...db.store import delete_handoff

    hid = request.path_params["handoff_id"]
    delete_handoff(_db_path(), hid)
    return RedirectResponse(url="/handoffs", status_code=303)


def handoffs_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(t("ho.title", lang), no_db_html(lang), "handoffs", lang, theme))

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
  <td><form method="post" action="/handoff/{_esc(dict(r)['id'])}/delete" style="display:inline" onsubmit="return confirm('{t('ho.confirm_delete', lang)}')"><button type="submit" class="btn btn-danger" style="padding:.2rem .5rem;font-size:.8rem">{t('common.delete', lang)}</button></form></td>
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
        return HTMLResponse(_layout("Handoff", no_db_html(lang), "handoffs", lang, theme))

    conn = get_connection(db)
    init_schema(conn)
    row = conn.execute("SELECT * FROM handoffs WHERE id=?", (hid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(
            _layout("Handoff", f'<div class="card"><p>{t("ho.not_found", lang, id=hid)}</p></div>', "handoffs", lang, theme)
        )

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
