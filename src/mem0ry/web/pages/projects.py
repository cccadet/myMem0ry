from __future__ import annotations

import html
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _icon, _layout, _memory_card, _tag
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
        f"""<tr class="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
  <td class="px-4 py-3 text-sm"><a href="/project/{html.escape(p['project_id'])}" class="font-mono font-medium text-primary-600 hover:underline dark:text-primary-300">{_esc(p['project_id'])}</a></td>
  <td class="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">{_esc(p.get('project_path'))}</td>
  <td class="px-4 py-3 text-sm font-medium">{p['mem_cnt']}</td>
  <td class="px-4 py-3 text-sm"><a href="/project/{html.escape(p['project_id'])}/observations" class="inline-flex items-center gap-1 text-primary-600 hover:underline dark:text-primary-300">{_icon('visibility', 'text-base', 16)}{p['obs_cnt']}</a></td>
</tr>"""
        for p in sorted_projects
    )

    body = f"""<h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("proj.global", lang)}</h2>
<div class="reveal mb-6 rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 shadow-sm transition hover:-translate-y-0.5 dark:bg-[var(--md-sys-color-surface-container)]">
  <a href="/project/global" class="inline-flex items-center gap-2 text-primary-600 hover:underline dark:text-primary-300">{_icon('public', 'text-base', 18)}{t("proj.global_count", lang, n=global_cnt)}</a>
</div>
<h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("proj.projects", lang)}</h2>
<div class="reveal overflow-hidden rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
<table class="w-full text-left text-sm">
<thead class="bg-slate-50 font-mono text-xs uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
<tr><th class="px-4 py-3">{t("proj.col_id", lang)}</th><th class="px-4 py-3">{t("proj.col_path", lang)}</th><th class="px-4 py-3">{t("proj.col_mem", lang)}</th><th class="px-4 py-3">{t("proj.col_obs", lang)}</th></tr>
</thead>
<tbody class="divide-y divide-[var(--md-sys-color-outline)]">
{rows_html if rows_html else f'<tr><td colspan="4" class="px-4 py-6 text-center text-slate-500 dark:text-slate-400">{t("proj.no_memories", lang)}</td></tr>'}
</tbody>
</table>
</div>"""

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

    export_btn = f'<form method="post" action="/memories/export" class="mb-4 inline"><input type="hidden" name="project_id" value="{html.escape(pid)}"><button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-3 py-1.5 text-sm font-semibold text-green-600 transition hover:bg-green-50 dark:border-green-900 dark:bg-slate-800 dark:text-green-400 dark:hover:bg-green-950">{_icon("download")}{t("proj.export", lang)}</button></form>'

    obs_link = ""
    if pid != "global" and obs_count > 0:
        obs_link = f'<a href="/project/{html.escape(pid)}/observations" class="mb-4 ml-2 inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">{_icon("visibility")}{t("obs.project_obs", lang)} ({obs_count})</a>'

    body = f"""<h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{_esc(pid)}</h2>
<div class="mb-4 flex flex-wrap gap-2">{scope_html}</div>
{export_btn} {obs_link}
<h3 class="mb-3 text-lg font-semibold text-[var(--md-sys-color-on-surface)]">{t("proj.memories_n", lang, n=len(rows))}</h3>
<div class="space-y-3">{cards_html if cards_html else f'<div class="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">{t("proj.no_memories", lang)}</div>'}</div>"""

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
        body = f"""<h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{_esc(pid)} — {t("obs.project_obs", lang)}</h2>
<p class="mb-4"><a href="/project/{html.escape(pid)}" class="inline-flex items-center gap-1 text-primary-600 hover:underline dark:text-primary-300">{_icon("arrow_back", "text-base", 16)}{t("common.back", lang)}</a></p>
<div class="reveal flex flex-col items-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-10 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
  {_icon('visibility_off', 'text-5xl mb-3 opacity-50', 48)}
  <p>{t("obs.none_for_project", lang)}</p>
</div>"""
        return HTMLResponse(_layout(f"{t('obs.project_obs', lang)}: {pid}", body, "projects", lang, theme))

    kind_icons = {
        "session-start": "rocket_launch",
        "user-prompt": "chat_bubble_outline",
        "post-tool-use": "build",
        "pre-compact": "inventory_2",
        "session-end": "flag",
        "log": "sticky_note_2",
        "other": "push_pin",
    }

    cards_html = ""
    for r in obs_rows:
        row = dict(r)
        oid = row["id"]
        kind = row.get("kind") or "other"
        icon = kind_icons.get(kind, "push_pin")
        title = _esc(row.get("title") or oid[:16])
        agent = _esc(row.get("agent") or "—")
        created = (row.get("created_at") or "")[:19]
        body_preview = _esc((row.get("body") or "")[:150])
        if len(row.get("body") or "") > 150:
            body_preview += "…"

        cards_html += f"""<article class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <div class="flex items-start gap-3">
    <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">{_icon(icon, 'text-xl', 22)}</span>
    <div class="min-w-0 flex-1">
      <div class="mb-1 flex flex-wrap items-center gap-2">
        <a href="/observation/{_esc(oid)}" class="text-base font-semibold text-[var(--md-sys-color-on-surface)] hover:text-primary-600 dark:hover:text-primary-300">{title}</a>
        {_tag(kind, kind)}
      </div>
      <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-mono text-slate-500 dark:text-slate-400">
        <span>{agent}</span>
        <span class="h-1 w-1 rounded-full bg-slate-400"></span>
        <span>{created}</span>
      </div>
      {f'<div class="mt-2 line-clamp-2 text-sm text-slate-600 dark:text-slate-400">{body_preview}</div>' if body_preview.strip() else ''}
    </div>
  </div>
</article>"""

    body = f"""<h2 class="mb-3 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{_esc(pid)} — {t("obs.project_obs", lang)}</h2>
<p class="mb-4"><a href="/project/{html.escape(pid)}" class="inline-flex items-center gap-1 text-primary-600 hover:underline dark:text-primary-300">{_icon("arrow_back", "text-base", 16)}{t("common.back", lang)}</a></p>
<div class="reveal mb-4 text-sm text-slate-500 dark:text-slate-400">{len(obs_rows)} {t("obs.total", lang)}</div>
<div class="space-y-3">{cards_html}</div>"""

    return HTMLResponse(_layout(f"{t('obs.project_obs', lang)}: {pid}", body, "projects", lang, theme))
