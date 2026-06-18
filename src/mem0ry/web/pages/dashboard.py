from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _layout, _memory_card
from .shared import ago_label, comp_bar


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

    total = conn.execute(
        "SELECT count(*) FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '')"
    ).fetchone()[0]
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
    from ..templates import _esc

    if open_ho:
        ho_cards = "".join(
            f"""<a href="/handoff/{_esc(dict(r)['id'])}" class="ho">
        <div class="top">
          <span class="dotmark"></span>
          <span class="repo">{_esc(dict(r).get('project_id') or '—')}</span>
          <span class="ago">{ago_label(dict(r).get('created_at'), lang)}</span>
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
  {comp_bar(list(by_scope), "scope", lang)}
  {comp_bar(list(by_type), "type", lang)}
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
