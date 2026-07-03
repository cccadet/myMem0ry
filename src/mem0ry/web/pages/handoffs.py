from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _icon, _layout, _tag
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
        active = status_filter == s
        cnt = counts.get(s, "") if s else sum(counts.values())
        cls = "rounded-lg px-3 py-1.5 text-sm font-medium transition " + ("bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300" if active else "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800")
        status_tabs += f'<a href="/handoffs{"?status="+s if s else ""}" class="{cls}">{label} ({cnt})</a> '

    _STATUS_COLOR = {"open": "muted", "accepted": "project", "expired": "log"}

    rows_html = "".join(
        f"""<tr class="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
  <td class="px-4 py-3 text-sm font-mono"><a href="/handoff/{_esc(dict(r)['id'])}" class="text-primary-600 hover:underline dark:text-primary-300">{_esc(dict(r)['id'])}</a></td>
  <td class="px-4 py-3">{_tag(_STATUS_COLOR.get(dict(r)['status'], 'log'), dict(r)['status'])}</td>
  <td class="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">{_esc(dict(r).get('from_agent'))}</td>
  <td class="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">{_esc(dict(r).get('project_id'))}</td>
  <td class="max-w-xs truncate px-4 py-3 text-sm">{_esc((dict(r).get('summary') or '')[:120])}</td>
  <td class="px-4 py-3 text-sm font-mono text-slate-500 dark:text-slate-400">{(dict(r).get('created_at') or '')[:16]}</td>
  <td class="px-4 py-3"><form method="post" action="/handoff/{_esc(dict(r)['id'])}/delete" class="inline" onsubmit="return confirm('{t('ho.confirm_delete', lang)}')"><button type="submit" class="inline-flex items-center gap-1 rounded border border-red-200 px-2 py-1 text-xs font-semibold text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950">{_icon('delete', 'text-base', 14)}</button></form></td>
</tr>"""
        for r in rows
    )

    body = f"""<h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("ho.title", lang)}</h2>
<div class="mb-4 flex flex-wrap gap-1">{status_tabs}</div>
<div class="reveal overflow-hidden rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
<table class="w-full text-left text-sm">
<thead class="bg-slate-50 font-mono text-xs uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
<tr><th class="px-4 py-3">{t("ho.col_id", lang)}</th><th class="px-4 py-3">{t("ho.col_status", lang)}</th><th class="px-4 py-3">{t("ho.col_from", lang)}</th><th class="px-4 py-3">{t("ho.col_project", lang)}</th><th class="px-4 py-3">{t("ho.col_summary", lang)}</th><th class="px-4 py-3">{t("ho.col_created", lang)}</th><th class="px-4 py-3"></th></tr>
</thead>
<tbody class="divide-y divide-[var(--md-sys-color-outline)]">
{rows_html if rows_html else f'<tr><td colspan="7" class="px-4 py-6 text-center text-slate-500 dark:text-slate-400">{t("ho.none", lang)}</td></tr>'}
</tbody>
</table>
</div>"""

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
            _layout("Handoff", f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"><p class="text-slate-600 dark:text-slate-400">{t("ho.not_found", lang, id=hid)}</p></div>', "handoffs", lang, theme)
        )

    ho = dict(row)
    oq: list[str] = json.loads(ho.get("open_questions") or "[]")
    ns: list[str] = json.loads(ho.get("next_steps") or "[]")

    _STATUS_COLOR = {"open": "muted", "accepted": "project", "expired": "log"}
    status_tag = _tag(_STATUS_COLOR.get(ho["status"], "log"), ho["status"])

    oq_html = "".join(f'<li class="ml-5 list-disc text-slate-700 dark:text-slate-300">{_esc(qi)}</li>' for qi in oq) if oq else f'<li class="ml-5 list-disc text-sm text-slate-500 dark:text-slate-400">{t("ho.none_item", lang)}</li>'
    ns_html = "".join(f'<li class="ml-5 list-disc text-slate-700 dark:text-slate-300">{_esc(s)}</li>' for s in ns) if ns else f'<li class="ml-5 list-disc text-sm text-slate-500 dark:text-slate-400">{t("ho.none_item", lang)}</li>'

    actions: list[str] = []
    if ho["status"] == "open":
        actions.append(
            f'<form method="post" action="/handoff/{hid}/close" class="inline" '
            f'onsubmit="return confirm(\'{t("ho.confirm_close", lang)}\')">'
            f'<button type="submit" class="inline-flex items-center gap-1 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700">{_icon("check")}{t("ho.close", lang)}</button></form>'
        )
    actions.append(
        f'<form method="post" action="/handoff/{hid}/delete" class="inline" '
        f'onsubmit="return confirm(\'{t("ho.confirm_delete", lang)}\')">'
        f'<button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-semibold text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:bg-slate-800 dark:text-red-400 dark:hover:bg-red-950">{_icon("delete")}{t("common.delete", lang)}</button></form>'
    )
    actions_html = " ".join(actions)

    body = f"""<div class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">Handoff {_esc(hid)}</h2>
  <div class="mb-3">{status_tag}</div>
  <div class="space-y-1 text-sm text-slate-600 dark:text-slate-400">
    <div class="flex flex-wrap gap-x-4 gap-y-1">
      <span><strong class="text-slate-800 dark:text-slate-200">{t("ho.from", lang)}:</strong> {_esc(ho.get('from_agent'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("ho.created", lang)}:</strong> {(ho.get('created_at') or '')[:19]}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("ho.expires", lang)}:</strong> {(ho.get('expires_at') or '')[:10]}</span>
    </div>
    <div class="flex flex-wrap gap-x-4 gap-y-1">
      <span><strong class="text-slate-800 dark:text-slate-200">{t("ho.project", lang)}:</strong> {_esc(ho.get('project_id'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("ho.path", lang)}:</strong> {_esc(ho.get('project_path'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("ho.session", lang)}:</strong> {_esc(ho.get('session_id'))}</span>
    </div>
    {f'<div><strong class="text-slate-800 dark:text-slate-200">{t("ho.accepted_by", lang)}:</strong> {_esc(ho.get("accepted_by"))} @ {(ho.get("accepted_at") or "")[:19]}</div>' if ho.get("accepted_by") else ""}
  </div>
  <div class="mt-4 flex flex-wrap gap-2">{actions_html}</div>
</div>
<h3 class="mb-2 mt-6 text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("ho.summary", lang)}</h3>
<pre class="overflow-x-auto whitespace-pre-wrap rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-4 text-sm leading-relaxed text-slate-800 shadow-sm dark:bg-[var(--md-sys-color-surface-container-high)] dark:text-slate-200">{_esc(ho.get('summary') or '')}</pre>
<h3 class="mb-2 mt-6 text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("ho.open_questions", lang)}</h3>
<ul class="space-y-1 rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 dark:bg-[var(--md-sys-color-surface-container)]">{oq_html}</ul>
<h3 class="mb-2 mt-6 text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("ho.next_steps", lang)}</h3>
<ul class="space-y-1 rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 dark:bg-[var(--md-sys-color-surface-container)]">{ns_html}</ul>"""

    return HTMLResponse(_layout(f"Handoff: {hid}", body, "handoffs", lang, theme))
