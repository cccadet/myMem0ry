from __future__ import annotations

import html
import json
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _icon, _layout
from .shared import no_db_html

_JSON_MEDIA_TYPE = "application/json"


def export_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout(t("exp.title", lang), no_db_html(lang), "export", lang, theme))

    conn = get_connection(db)
    init_schema(conn)

    projects = conn.execute(
        "SELECT project_id, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') "
        "GROUP BY project_id ORDER BY cnt DESC"
    ).fetchall()

    total_mem = conn.execute(
        "SELECT count(*) FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '')"
    ).fetchone()[0]

    global_cnt = conn.execute(
        "SELECT count(*) FROM memories WHERE scope='global' AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '')"
    ).fetchone()[0]

    scopes = conn.execute(
        "SELECT scope, count(*) as cnt FROM memories WHERE deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '') GROUP BY scope"
    ).fetchall()

    conn.close()

    project_options = "".join(
        f'<label class="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-2.5 transition hover:bg-slate-50 dark:bg-[var(--md-sys-color-surface-container)] dark:hover:bg-slate-800">'
        f'<input type="checkbox" name="project_ids" value="{html.escape(dict(r)["project_id"])}" class="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-800">'
        f'<span class="flex-1 truncate font-mono text-xs text-slate-700 dark:text-slate-300">{_esc(dict(r)["project_id"])}</span>'
        f'<span class="text-xs text-slate-500 dark:text-slate-400">{dict(r)["cnt"]}</span>'
        f'</label>'
        for r in projects
    )

    scope_options = "".join(
        f'<label class="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-2 transition hover:bg-slate-50 dark:bg-[var(--md-sys-color-surface-container)] dark:hover:bg-slate-800">'
        f'<input type="checkbox" name="scopes" value="{r["scope"]}" class="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-800">'
        f'{_tag_html(r["scope"], r["scope"])}'
        f'<span class="ml-auto text-xs text-slate-500 dark:text-slate-400">{r["cnt"]}</span>'
        f'</label>'
        for r in scopes
    )

    body = f"""<h2 class="mb-2 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("exp.title", lang)}</h2>
<p class="mb-6 text-sm text-slate-500 dark:text-slate-400">{t("exp.description", lang)}</p>

<form method="post" action="/memories/export" id="export-form" class="space-y-5">
  <div class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
    <h3 class="mb-3 text-sm font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("exp.quick_export", lang)}</h3>
    <div class="flex flex-wrap gap-2">
      <button type="submit" name="scope" value="" class="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-600 transition hover:bg-green-50 dark:border-green-900 dark:bg-slate-800 dark:text-green-400 dark:hover:bg-green-950">
        {_icon("download")}{t("exp.all_memories", lang)} ({total_mem})
      </button>
      <button type="submit" name="scope" value="global" class="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-600 transition hover:bg-green-50 dark:border-green-900 dark:bg-slate-800 dark:text-green-400 dark:hover:bg-green-950">
        {_icon("download")}{t("exp.global_only", lang)} ({global_cnt})
      </button>
    </div>
  </div>

  <div class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
    <h3 class="mb-3 text-sm font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("exp.by_scope", lang)}</h3>
    <div class="mb-4 flex flex-wrap gap-2">
      {scope_options}
    </div>
    <button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-600 transition hover:bg-green-50 disabled:opacity-50 dark:border-green-900 dark:bg-slate-800 dark:text-green-400 dark:hover:bg-green-950" id="scope-export-btn" disabled>
      {_icon("download")}{t("exp.export_selected_scopes", lang)}
    </button>
  </div>

  <div class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
    <h3 class="mb-3 text-sm font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("exp.by_project", lang)}</h3>
    {f'<div class="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{project_options}</div>' if project_options else f'<p class="text-sm text-slate-500 dark:text-slate-400">{t("exp.no_projects", lang)}</p>'}
    <button type="submit" class="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-3 py-2 text-sm font-semibold text-green-600 transition hover:bg-green-50 disabled:opacity-50 dark:border-green-900 dark:bg-slate-800 dark:text-green-400 dark:hover:bg-green-950" id="project-export-btn" disabled>
      {_icon("download")}{t("exp.export_selected_projects", lang)}
    </button>
  </div>
</form>

<script>window.EXPORT_EXPORTING_LABEL = {json.dumps(t('exp.exporting', lang))};</script>
<script src="/static/js/export.js"></script>"""

    return HTMLResponse(_layout(t("exp.title", lang), body, "export", lang, theme))


def _tag_html(scope: str, label: str) -> str:
    from ..templates import _tag

    return _tag(scope, label)


async def export_memories_page(request: Request) -> Response:
    from ...db.store import export_handoffs, export_memories

    form = await request.form()
    ids = [str(v) for v in form.getlist("ids")]
    scope_val = str(form.get("scope", ""))
    project_id_val = str(form.get("project_id", ""))
    project_ids = [str(v) for v in form.getlist("project_ids")]
    scopes = [str(v) for v in form.getlist("scopes")]

    filters: dict[str, Any] = {}
    if ids:
        filters["memory_ids"] = ids
    elif project_ids:
        all_memories: list[dict[str, Any]] = []
        all_handoffs: list[dict[str, Any]] = []
        for pid in project_ids:
            mem_data = export_memories(_db_path(), project_id=pid)
            all_memories.extend(mem_data.get("memories", []))
            ho_data = export_handoffs(_db_path(), project_id=pid)
            all_handoffs.extend(ho_data)
        data = {"memories": all_memories, "handoffs": all_handoffs}
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        filename = "mem0ry-export-projects.json"
        return Response(
            content=json_str,
            media_type=_JSON_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif scopes:
        all_memories = []
        all_handoffs = []
        for sc in scopes:
            mem_data = export_memories(_db_path(), scope=sc)
            all_memories.extend(mem_data.get("memories", []))
        data = {"memories": all_memories, "handoffs": all_handoffs}
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        filename = f"mem0ry-export-{'-'.join(scopes)}.json"
        return Response(
            content=json_str,
            media_type=_JSON_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif scope_val:
        filters["scope"] = scope_val
    elif project_id_val:
        filters["project_id"] = project_id_val

    data = export_memories(_db_path(), **filters)

    export_pid: str | None = project_id_val or None
    handoffs = export_handoffs(_db_path(), project_id=export_pid)
    if handoffs:
        data["handoffs"] = handoffs

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    filename = "mem0ry-export.json"
    return Response(
        content=json_str,
        media_type=_JSON_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def import_memories_page(request: Request) -> Any:
    from ...db.store import import_handoffs, import_memories

    lang = get_lang(request)
    form = await request.form()
    upload = form.get("file")
    pid_raw = form.get("project_id_override", "")
    project_id_override: str | None = str(pid_raw) if pid_raw else None

    if not upload or not hasattr(upload, "read"):
        return RedirectResponse(url=f"/import?msg={html.escape(t('imp.no_file', lang))}&type=error", status_code=303)

    content_bytes = await upload.read()
    try:
        data = json.loads(content_bytes)
    except json.JSONDecodeError as e:
        return RedirectResponse(url=f"/import?msg={html.escape(t('imp.invalid_json', lang, err=str(e)))}&type=error", status_code=303)

    mem_result = import_memories(_db_path(), data, project_id_override=project_id_override)
    ho_result = {"imported": 0, "skipped": 0}
    if data.get("handoffs"):
        ho_result = import_handoffs(
            _db_path(), data["handoffs"], project_id_override=project_id_override
        )

    msg = t(
        "imp.result",
        lang,
        mem=mem_result["imported"],
        ho=ho_result["imported"],
        mem_skip=mem_result["skipped"],
        ho_skip=ho_result["skipped"],
    )
    return RedirectResponse(url=f"/import?msg={html.escape(msg)}&type=success", status_code=303)


def import_page(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    theme = get_theme(request)
    msg = request.query_params.get("msg", "")
    msg_type = request.query_params.get("type", "success")

    msg_html = ""
    if msg:
        border = "border-green-300 dark:border-green-800" if msg_type == "success" else "border-red-300 dark:border-red-800"
        bg = "bg-green-50 dark:bg-green-950/30" if msg_type == "success" else "bg-red-50 dark:bg-red-950/30"
        icon = "check_circle" if msg_type == "success" else "error"
        text = "text-green-800 dark:text-green-200" if msg_type == "success" else "text-red-800 dark:text-red-200"
        msg_html = f'''<div class="reveal mb-4 rounded-xl border {border} {bg} p-4 shadow-sm">
  <div class="flex items-center gap-3">
    {_icon(icon, 'text-xl', 22)}
    <p class="text-sm {text}">{html.escape(msg)}</p>
  </div>
</div>'''

    body = f"""<h2 class="mb-2 text-xl font-bold text-[var(--md-sys-color-on-surface)]">{t("imp.title", lang)}</h2>
{msg_html}
<div class="reveal rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <form method="post" action="/memories/import" enctype="multipart/form-data" id="import-form" class="space-y-5">
    <div>
      <label class="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-400">{t("imp.select_file", lang)}</label>
      <div id="drop-zone" class="cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center transition hover:border-primary-400 hover:bg-primary-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-primary-700 dark:hover:bg-primary-950/20">
        <div class="mb-2 text-slate-400">{_icon('upload_file', 'text-5xl', 48)}</div>
        <div class="text-sm text-slate-600 dark:text-slate-400">{t("imp.drop_hint", lang)}</div>
        <div class="mt-1 text-xs text-slate-400 dark:text-slate-500">{t("imp.or_click", lang)}</div>
        <input type="file" name="file" id="file-input" accept=".json" required class="hidden">
        <div id="file-name" class="mt-3 hidden font-mono text-sm"></div>
      </div>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-400">{t("imp.override", lang)}</label>
      <input type="text" name="project_id_override" placeholder="e.g. https://github.com/org/repo" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-primary-900">
      <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">{t("imp.override_hint", lang)}</div>
    </div>
    <div class="flex flex-wrap items-center gap-3">
      <button type="submit" class="inline-flex items-center gap-1 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:opacity-50" id="import-btn" disabled>
        {_icon("upload")}{t("imp.button", lang)}
      </button>
      <span id="import-status" class="hidden text-sm text-slate-500 dark:text-slate-400"></span>
    </div>
  </form>
</div>
<div class="reveal mt-4 rounded-xl border border-[var(--md-sys-color-outline)] bg-[var(--md-sys-color-surface-container-low)] p-5 shadow-sm dark:bg-[var(--md-sys-color-surface-container)]">
  <h3 class="mb-2 text-sm font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400">{t("imp.help_title", lang)}</h3>
  <ul class="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
    <li>{t("imp.help_1", lang)}</li>
    <li>{t("imp.help_2", lang)}</li>
    <li>{t("imp.help_3", lang)}</li>
  </ul>
</div>
<script>
window.IMPORT_INVALID_TYPE = {json.dumps(t('imp.invalid_type', lang))};
window.IMPORT_IMPORTING_LABEL = {json.dumps(t('imp.importing', lang))};
</script>
<script src="/static/js/import.js"></script>"""

    return HTMLResponse(_layout(t("imp.title", lang), body, "import-page", lang, theme))
