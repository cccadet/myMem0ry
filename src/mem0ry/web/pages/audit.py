from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _TITLE_AUDIT, _db_path, _esc, _layout
from .shared import no_db_html, target_link


def audit_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(_TITLE_AUDIT, no_db_html(lang), "audit", lang, theme))

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
  <td>{target_link(dict(row))}</td>
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
