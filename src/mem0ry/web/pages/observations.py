from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _icon, _layout, _tag
from .shared import delete_form, no_db_html


def observation_detail(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    oid = request.path_params["observation_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Observation", no_db_html(lang), "dashboard", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(
            _layout("Observation", f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"><p class="text-slate-600 dark:text-slate-400">{t("obs.not_found", lang, id=oid)}</p></div>', "dashboard", lang, theme)
        )

    o = dict(row)
    body_text = _esc(o.get("body") or "")
    oid = o["id"]

    body = f"""<div class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{_esc(o.get('title') or o['id'])}</h2>
  <div class="mb-3">{_tag(o.get('kind', 'other'), o.get('kind', 'other'))}</div>
  <div class="space-y-1 text-sm text-slate-600 dark:text-slate-400">
    <div class="flex flex-wrap gap-x-4 gap-y-1">
      <span class="inline-flex items-center gap-1">{_icon("event", "text-xs", 14)}<strong class="text-slate-800 dark:text-slate-200">{t("mem.created", lang)}:</strong> {(o.get('created_at') or '')[:19]}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("obs.agent", lang)}:</strong> {_esc(o.get('agent'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("obs.session", lang)}:</strong> {_esc(o.get('session_id'))}</span>
    </div>
    <div class="flex flex-wrap gap-x-4 gap-y-1">
      <span><strong class="text-slate-800 dark:text-slate-200">{t("obs.project", lang)}:</strong> {_esc(o.get('project_id'))}</span>
      <span><strong class="text-slate-800 dark:text-slate-200">{t("obs.cwd", lang)}:</strong> {_esc(o.get('cwd'))}</span>
    </div>
  </div>
  <div class="mt-4">{delete_form(oid, 'observation', t("obs.confirm_delete", lang), t("common.delete", lang))}</div>
</div>
<h3 class="mb-2 mt-6 text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("obs.body", lang)}</h3>
<pre class="overflow-x-auto whitespace-pre-wrap rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-4 text-sm leading-relaxed text-slate-800 shadow-sm dark:bg-[var(--md-sys-color-surface-container-high)] dark:text-slate-200">{body_text if body_text else f'<em class="text-slate-500 dark:text-slate-400">{t("obs.empty", lang)}</em>'}</pre>"""

    return HTMLResponse(_layout(f"Observation: {o.get('title', oid)}", body, "dashboard", lang, theme))


def delete_observation_page(request: Request) -> Any:
    from ...db.store import delete_observation

    oid = request.path_params["observation_id"]
    delete_observation(_db_path(), oid)
    return RedirectResponse(url="/", status_code=303)
