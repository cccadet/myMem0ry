from __future__ import annotations

import html
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _layout, _memory_card, _tag
from .shared import no_db_html


def projects_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(t("nav.projects", lang), no_db_html(lang), "projects", lang, theme))

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
  <td><a href="/project/{html.escape(p['project_id'])}/observations">{p['obs_cnt']}</a></td>
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
        return HTMLResponse(_layout("Project", no_db_html(lang), "projects", lang, theme))

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

    obs_count = 0
    if pid != "global":
        obs_count = conn.execute(
            "SELECT count(*) FROM observations WHERE project_id=?", (pid,)
        ).fetchone()[0]

    conn.close()

    scope_html = " ".join(
        _tag(r["scope"], f'{r["scope"]} ({r["cnt"]})') for r in by_scope
    )

    cards_html = "".join(_memory_card(dict(r), lang) for r in rows)

    export_btn = f'<form method="post" action="/memories/export" style="margin-bottom:1rem;display:inline"><input type="hidden" name="project_id" value="{html.escape(pid)}"><button type="submit" class="btn btn-export">{t("proj.export", lang)}</button></form>'

    obs_link = ""
    if pid != "global" and obs_count > 0:
        obs_link = f'<a href="/project/{html.escape(pid)}/observations" class="btn" style="text-decoration:none;margin-bottom:1rem;display:inline-block">{t("obs.project_obs", lang)} ({obs_count})</a>'

    body = f"""<h2>{_esc(pid)}</h2>
<div>{scope_html}</div>
{export_btn} {obs_link}
<h2>{t("proj.memories_n", lang, n=len(rows))}</h2>
{cards_html if cards_html else f'<div class="card meta">{t("proj.no_memories", lang)}</div>'}"""

    return HTMLResponse(_layout(f"Project: {pid}", body, "projects", lang, theme))


def project_observations(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    pid = request.path_params["project_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout(t("obs.project_obs", lang), no_db_html(lang), "projects", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    obs_rows = conn.execute(
        "SELECT * FROM observations WHERE project_id=? ORDER BY created_at DESC LIMIT 200",
        (pid,),
    ).fetchall()
    conn.close()

    if not obs_rows:
        body = f"""<h2>{_esc(pid)} — {t("obs.project_obs", lang)}</h2>
<p><a href="/project/{html.escape(pid)}">← {t("common.back", lang)}</a></p>
<div class="empty-state">
  <div class="empty-state-icon">👁</div>
  <div class="empty-state-text">{t("obs.none_for_project", lang)}</div>
</div>"""
        return HTMLResponse(_layout(f"{t('obs.project_obs', lang)}: {pid}", body, "projects", lang, theme))

    kind_icons = {
        "session-start": "🚀",
        "user-prompt": "💬",
        "post-tool-use": "🔧",
        "pre-compact": "📦",
        "session-end": "🏁",
        "log": "📝",
        "other": "📌",
    }

    cards_html = ""
    for r in obs_rows:
        row = dict(r)
        oid = row["id"]
        kind = row.get("kind") or "other"
        icon = kind_icons.get(kind, "📌")
        title = _esc(row.get("title") or oid[:16])
        agent = _esc(row.get("agent") or "—")
        created = (row.get("created_at") or "")[:19]
        body_preview = _esc((row.get("body") or "")[:150])
        if len(row.get("body") or "") > 150:
            body_preview += "…"

        cards_html += f"""<article class="card reveal" style="margin-bottom:.8rem">
  <div style="display:flex;align-items:flex-start;gap:.7rem">
    <span style="font-size:1.3rem;flex-shrink:0">{icon}</span>
    <div style="flex:1;min-width:0">
      <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.3rem">
        <a href="/observation/{_esc(oid)}" style="font-weight:600;font-size:1rem">{title}</a>
        {_tag(kind, kind)}
      </div>
      <div class="meta row">
        <span>{agent}</span><span class="sep"></span>
        <span>{created}</span>
      </div>
      {f'<div class="snippet" style="margin-top:.4rem">{body_preview}</div>' if body_preview.strip() else ''}
    </div>
  </div>
</article>"""

    body = f"""<h2>{_esc(pid)} — {t("obs.project_obs", lang)}</h2>
<p><a href="/project/{html.escape(pid)}">← {t("common.back", lang)}</a></p>
<div class="meta" style="margin-bottom:1rem">{len(obs_rows)} {t("obs.total", lang)}</div>
{cards_html}"""

    return HTMLResponse(_layout(f"{t('obs.project_obs', lang)}: {pid}", body, "projects", lang, theme))
