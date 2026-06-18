from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _layout, _tag
from .shared import no_db_html


def trash_page(request: Request) -> HTMLResponse:
    from ...db.store import list_deleted_memories

    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(t("trash.title", lang), no_db_html(lang), "trash", lang, theme))

    conn = get_connection(db)
    init_schema(conn)
    conn.close()

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
