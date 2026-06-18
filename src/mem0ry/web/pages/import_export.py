from __future__ import annotations

import html
import json
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from ...db.connection import get_connection
from ...db.schema import init_schema
from ..i18n import get_lang, get_theme, t
from ..templates import _db_path, _esc, _layout
from .shared import no_db_html


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
        f'<label class="project-option" style="display:flex;align-items:center;gap:.5rem;padding:.5rem .7rem;'
        f'border:1px solid var(--border);border-radius:8px;cursor:pointer;transition:.15s">'
        f'<input type="checkbox" name="project_ids" value="{html.escape(dict(r)["project_id"])}" '
        f'style="accent-color:var(--accent)">'
        f'<span style="flex:1;font-family:var(--mono);font-size:.85rem">{_esc(dict(r)["project_id"])}</span>'
        f'<span class="meta">{dict(r)["cnt"]}</span>'
        f'</label>'
        for r in projects
    )

    scope_options = "".join(
        f'<label style="display:flex;align-items:center;gap:.5rem;padding:.4rem .6rem;'
        f'border:1px solid var(--border);border-radius:8px;cursor:pointer;transition:.15s">'
        f'<input type="checkbox" name="scopes" value="{r["scope"]}" style="accent-color:var(--accent)">'
        f'{_tag_html(r["scope"], r["scope"])}'
        f'<span class="meta">{r["cnt"]}</span>'
        f'</label>'
        for r in scopes
    )

    body = f"""<h2>{t("exp.title", lang)}</h2>
<p class="meta" style="margin-bottom:1.2rem">{t("exp.description", lang)}</p>

<form method="post" action="/memories/export" id="export-form">
  <div class="card" style="margin-bottom:1rem">
    <h3 style="margin-top:0">{t("exp.quick_export", lang)}</h3>
    <div style="display:flex;gap:.6rem;flex-wrap:wrap">
      <button type="submit" name="scope" value="" class="btn btn-export">
        ↓ {t("exp.all_memories", lang)} ({total_mem})
      </button>
      <button type="submit" name="scope" value="global" class="btn btn-export">
        ↓ {t("exp.global_only", lang)} ({global_cnt})
      </button>
    </div>
  </div>

  <div class="card" style="margin-bottom:1rem">
    <h3 style="margin-top:0">{t("exp.by_scope", lang)}</h3>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.8rem">
      {scope_options}
    </div>
    <button type="submit" class="btn btn-export" id="scope-export-btn" disabled>
      ↓ {t("exp.export_selected_scopes", lang)}
    </button>
  </div>

  <div class="card">
    <h3 style="margin-top:0">{t("exp.by_project", lang)}</h3>
    {f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.5rem;margin-bottom:.8rem">{project_options}</div>' if project_options else f'<p class="meta">{t("exp.no_projects", lang)}</p>'}
    <button type="submit" class="btn btn-export" id="project-export-btn" disabled>
      ↓ {t("exp.export_selected_projects", lang)}
    </button>
  </div>
</form>

<script>
(function() {{
  var scopeCheckboxes = document.querySelectorAll('input[name="scopes"]');
  var projectCheckboxes = document.querySelectorAll('input[name="project_ids"]');
  var scopeBtn = document.getElementById('scope-export-btn');
  var projectBtn = document.getElementById('project-export-btn');

  scopeCheckboxes.forEach(function(cb) {{
    cb.addEventListener('change', function() {{
      scopeBtn.disabled = !document.querySelectorAll('input[name="scopes"]:checked').length;
    }});
  }});

  projectCheckboxes.forEach(function(cb) {{
    cb.addEventListener('change', function() {{
      projectBtn.disabled = !document.querySelectorAll('input[name="project_ids"]:checked').length;
    }});
  }});

  document.getElementById('export-form').addEventListener('submit', function(e) {{
    var btn = e.submitter;
    if (btn) {{
      btn.innerHTML = '<span>⏳</span> {t("exp.exporting", lang)}...';
      btn.disabled = true;
    }}
  }});
}})();
</script>"""

    return HTMLResponse(_layout(t("exp.title", lang), body, "export", lang, theme))


def _tag_html(scope: str, label: str) -> str:
    from ..templates import _tag

    return _tag(scope, label)


async def export_memories_page(request: Request) -> Response:
    from ...db.store import export_memories, export_handoffs

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
            media_type="application/json",
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
            media_type="application/json",
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
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def import_memories_page(request: Request) -> Any:
    from ...db.store import import_memories, import_handoffs

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
        border_color = "var(--green)" if msg_type == "success" else "var(--red)"
        bg_color = "var(--green-soft)" if msg_type == "success" else "var(--red-soft)"
        icon = "✓" if msg_type == "success" else "⚠"
        msg_html = f'''<div class="card" style="border-color:{border_color};background:{bg_color}">
  <div style="display:flex;align-items:center;gap:.6rem">
    <span style="font-size:1.3rem">{icon}</span>
    <p style="margin:0">{html.escape(msg)}</p>
  </div>
</div>'''

    body = f"""<h2>{t("imp.title", lang)}</h2>
{msg_html}
<div class="card" style="margin-top:1.2rem">
  <form method="post" action="/memories/import" enctype="multipart/form-data" id="import-form">
    <div style="margin-bottom:1.2rem">
      <label style="display:block;color:var(--text-2);margin-bottom:.5rem;font-weight:600">{t("imp.select_file", lang)}</label>
      <div id="drop-zone" style="border:2px dashed var(--border-strong);border-radius:12px;padding:2rem;text-align:center;
        background:var(--surface);cursor:pointer;transition:.2s">
        <div style="font-size:2.5rem;margin-bottom:.5rem;opacity:.5">📁</div>
        <div style="color:var(--text-2);margin-bottom:.5rem">{t("imp.drop_hint", lang)}</div>
        <div style="color:var(--text-3);font-size:.85rem">{t("imp.or_click", lang)}</div>
        <input type="file" name="file" id="file-input" accept=".json" required
          style="display:none">
        <div id="file-name" style="margin-top:.8rem;color:var(--accent);font-family:var(--mono);font-size:.9rem;display:none"></div>
      </div>
    </div>
    <div style="margin-bottom:1.2rem">
      <label style="display:block;color:var(--text-2);margin-bottom:.5rem;font-weight:600">{t("imp.override", lang)}</label>
      <input type="text" name="project_id_override" placeholder="e.g. https://github.com/org/repo"
        style="max-width:100%;width:100%">
      <div style="color:var(--text-3);font-size:.82rem;margin-top:.3rem">{t("imp.override_hint", lang)}</div>
    </div>
    <div style="display:flex;gap:.6rem;align-items:center">
      <button type="submit" class="btn" id="import-btn" disabled style="display:flex;align-items:center;gap:.4rem">
        <span>↑</span> {t("imp.button", lang)}
      </button>
      <span id="import-status" class="meta" style="display:none"></span>
    </div>
  </form>
</div>
<div class="card" style="margin-top:1rem">
  <h3 style="margin-top:0">{t("imp.help_title", lang)}</h3>
  <ul style="padding-left:1.2rem;color:var(--text-2);line-height:1.7">
    <li>{t("imp.help_1", lang)}</li>
    <li>{t("imp.help_2", lang)}</li>
    <li>{t("imp.help_3", lang)}</li>
  </ul>
</div>
<script>
(function() {{
  var dropZone = document.getElementById('drop-zone');
  var fileInput = document.getElementById('file-input');
  var fileName = document.getElementById('file-name');
  var importBtn = document.getElementById('import-btn');
  var form = document.getElementById('import-form');

  dropZone.addEventListener('click', function() {{ fileInput.click(); }});

  dropZone.addEventListener('dragover', function(e) {{
    e.preventDefault();
    dropZone.style.borderColor = 'var(--accent)';
    dropZone.style.background = 'var(--accent-soft)';
  }});

  dropZone.addEventListener('dragleave', function(e) {{
    e.preventDefault();
    dropZone.style.borderColor = 'var(--border-strong)';
    dropZone.style.background = 'var(--surface)';
  }});

  dropZone.addEventListener('drop', function(e) {{
    e.preventDefault();
    dropZone.style.borderColor = 'var(--border-strong)';
    dropZone.style.background = 'var(--surface)';
    if (e.dataTransfer.files.length) {{
      fileInput.files = e.dataTransfer.files;
      showFile(e.dataTransfer.files[0]);
    }}
  }});

  fileInput.addEventListener('change', function() {{
    if (fileInput.files.length) showFile(fileInput.files[0]);
  }});

  function showFile(file) {{
    if (!file.name.endsWith('.json')) {{
      fileName.textContent = '⚠ {t("imp.invalid_type", lang)}';
      fileName.style.color = 'var(--red)';
      importBtn.disabled = true;
    }} else {{
      fileName.textContent = '✓ ' + file.name + ' (' + formatSize(file.size) + ')';
      fileName.style.color = 'var(--green)';
      importBtn.disabled = false;
    }}
    fileName.style.display = 'block';
  }}

  function formatSize(bytes) {{
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }}

  form.addEventListener('submit', function() {{
    importBtn.disabled = true;
    importBtn.innerHTML = '<span>⏳</span> {t("imp.importing", lang)}...';
  }});
}})();
</script>"""

    return HTMLResponse(_layout(t("imp.title", lang), body, "import-page", lang, theme))
