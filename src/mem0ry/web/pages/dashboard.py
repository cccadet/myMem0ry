from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _icon, _layout, _memory_card
from .shared import ago_label, comp_bar


def dashboard(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()
    body_parts: list[str] = []

    if not db.exists():
        body_parts.append(f'<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900"><p class="text-slate-600 dark:text-slate-400">{t("common.no_db_hint", lang)}</p></div>')
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

    from ..templates import _esc

    if open_ho:
        ho_cards = "".join(
            f"""<a href="/handoff/{_esc(dict(r)['id'])}" class="reveal block rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container)] p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-primary-300 hover:shadow-md dark:hover:border-primary-700">
        <div class="mb-2 flex items-center gap-2">
          <span class="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_0_3px_rgba(34,197,94,0.25)]"></span>
          <span class="flex-1 truncate font-mono text-xs text-slate-500 dark:text-slate-400">{_esc(dict(r).get('project_id') or '—')}</span>
          <span class="font-mono text-xs text-slate-400 dark:text-slate-500">{ago_label(dict(r).get('created_at'), lang)}</span>
        </div>
        <div class="line-clamp-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">{_esc((dict(r).get('summary') or '')[:160])}</div>
      </a>"""
            for r in open_ho
        )
        body_parts.append(f"""<section class="reveal overflow-hidden rounded-2xl border border-[var(--md-sys-color-outline)] bg-gradient-to-b from-primary-50/50 to-[var(--md-sys-color-surface-container-low)] shadow-sm dark:from-primary-950/30 dark:to-[var(--md-sys-color-surface-container)]">
    <div class="flex flex-wrap items-center gap-3 border-b border-[var(--md-sys-color-outline)] px-5 py-4">
      <span class="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("dash.resume_k", lang)}</span>
      <h2 class="text-lg font-bold text-[var(--md-sys-color-on-surface)]">{t("dash.resume_title", lang)}</h2>
      <span class="inline-flex items-center rounded-full border border-primary-200 bg-primary-50 px-2.5 py-0.5 text-xs font-semibold text-primary-700 dark:border-primary-900 dark:bg-primary-950 dark:text-primary-300">{handoffs_open} {t("ho.open", lang).lower()}</span>
      <span class="flex-1"></span>
      <a href="/handoffs?status=open" class="inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:underline dark:text-primary-300">{t("dash.view_all_handoffs", lang)}{_icon('arrow_forward', 'text-base', 16)}</a>
    </div>
    <div class="grid gap-4 p-5 sm:grid-cols-2">{ho_cards}</div>
  </section>""")

    body_parts.append(f"""<section class="reveal grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
  <div class="rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 shadow-sm transition hover:-translate-y-0.5 dark:bg-[var(--md-sys-color-surface-container)]">
    <div class="font-mono text-3xl font-bold text-[var(--md-sys-color-on-surface)]">{total}</div>
    <div class="mt-1 text-sm text-slate-500 dark:text-slate-400">{t("dash.memories", lang)}</div>
  </div>
  <div class="rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 shadow-sm transition hover:-translate-y-0.5 dark:bg-[var(--md-sys-color-surface-container)]">
    <div class="font-mono text-3xl font-bold text-[var(--md-sys-color-on-surface)]">{len(projects)}</div>
    <div class="mt-1 text-sm text-slate-500 dark:text-slate-400">{t("dash.projects", lang)}</div>
  </div>
  <a href="/handoffs?status=open" class="reveal rounded-xl border border-primary-200 bg-gradient-to-b from-primary-50 to-[var(--md-sys-color-surface-container-low)] p-4 shadow-sm transition hover:-translate-y-0.5 dark:border-primary-900 dark:from-primary-950/40 dark:to-[var(--md-sys-color-surface-container)]">
    <div class="font-mono text-3xl font-bold text-primary-700 dark:text-primary-300">{handoffs_open}</div>
    <div class="mt-1 text-sm text-slate-500 dark:text-slate-400">{t("dash.open_handoffs", lang)}</div>
  </a>
  <div class="rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-4 shadow-sm transition hover:-translate-y-0.5 dark:bg-[var(--md-sys-color-surface-container)]">
    <div class="font-mono text-3xl font-bold text-slate-400 dark:text-slate-500">{evolutions}</div>
    <div class="mt-1 text-sm text-slate-500 dark:text-slate-400">{t("dash.evolved_facts", lang)}</div>
  </div>
</section>
<div class="mt-3 inline-flex items-center gap-2 font-mono text-xs text-slate-500 dark:text-slate-400">
  {_icon('database', 'text-xs', 14)}{t("dash.schema", lang)} <strong class="text-slate-700 dark:text-slate-300">v{schema_ver}</strong> · {t("dash.store_healthy", lang)}
</div>""")

    body_parts.append(f"""<section class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <div class="grid gap-8 md:grid-cols-2">
    {comp_bar(list(by_scope), "scope", lang)}
    {comp_bar(list(by_type), "type", lang)}
  </div>
</section>""")

    cards_html = "".join(_memory_card(dict(r), lang) for r in recent)
    body_parts.append(f"""<div class="reveal mb-4 mt-8 flex items-center gap-3">
    <h2 class="text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("dash.recent", lang)}</h2>
    <span class="flex-1"></span>
    <span class="inline-flex overflow-hidden rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800">
      <span class="cursor-pointer bg-primary-100 px-3 py-1 text-sm font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300">{t("dash.all", lang)}</span>
      <a href="/search?pinned=1" class="cursor-pointer px-3 py-1 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800">{t("dash.pinned", lang)}</a>
    </span>
  </div>
  <div id="mem-list" class="space-y-3">{cards_html}</div>""")

    return HTMLResponse(_layout("Dashboard", "\n".join(body_parts), "dashboard", lang, theme))
