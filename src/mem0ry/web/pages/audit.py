from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _TITLE_AUDIT, _db_path, _layout
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
        f"""<tr class="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
  <td class="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">{(dict(row).get('created_at') or '')[:19]}</td>
  <td class="px-4 py-3 text-sm font-medium">{dict(row)['action']}</td>
  <td class="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{dict(row)['target_type']}</td>
  <td class="px-4 py-3 text-sm">{target_link(dict(row))}</td>
  <td class="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">{dict(row).get('agent')}</td>
  <td class="max-w-xs truncate px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{dict(row).get('details')}</td>
</tr>"""
        for row in rows
    )

    body = f"""<h2 class="mb-4 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("audit.title", lang)} ({t("audit.entries", lang, n=len(rows))})</h2>
<div class="reveal overflow-hidden rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
<table class="w-full text-left text-sm">
<thead class="bg-slate-50 font-mono text-xs uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
<tr><th class="px-4 py-3">{t("audit.time", lang)}</th><th class="px-4 py-3">{t("audit.action", lang)}</th><th class="px-4 py-3">{t("audit.type", lang)}</th><th class="px-4 py-3">{t("audit.target", lang)}</th><th class="px-4 py-3">{t("audit.agent", lang)}</th><th class="px-4 py-3">{t("audit.details", lang)}</th></tr>
</thead>
<tbody class="divide-y divide-[var(--md-sys-color-outline)]">
{rows_html}
</tbody>
</table>
</div>"""

    return HTMLResponse(_layout(_TITLE_AUDIT, body, "audit", lang, theme))
