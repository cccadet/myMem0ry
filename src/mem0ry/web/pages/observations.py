from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _layout, _tag
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
            _layout("Observation", f'<div class="card"><p>{t("obs.not_found", lang, id=oid)}</p></div>', "dashboard", lang, theme)
        )

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
  <div style="margin-top:.5rem">{delete_form(oid, 'observation', t("obs.confirm_delete", lang), t("common.delete", lang))}</div>
</div>
<h3>{t("obs.body", lang)}</h3>
<pre>{body_text if body_text else f'<em class="meta">{t("obs.empty", lang)}</em>'}</pre>"""

    return HTMLResponse(_layout(f"Observation: {o.get('title', oid)}", body, "dashboard", lang, theme))


def delete_observation_page(request: Request) -> Any:
    from ...db.store import delete_observation

    oid = request.path_params["observation_id"]
    delete_observation(_db_path(), oid)
    return RedirectResponse(url="/", status_code=303)
