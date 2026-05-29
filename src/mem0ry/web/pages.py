from __future__ import annotations

import html
import json
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..db.connection import get_connection
from ..db.schema import init_schema
from .templates import (
    _TITLE_AUDIT,
    _NO_DB,
    _db_path,
    _esc,
    _layout,
    _memory_card,
    _tag,
)


def _delete_form(target_id: str, target_type: str, label: str) -> str:
    action = f"/{target_type}/{target_id}/delete"
    return (
        f'<form method="post" action="{action}" '
        f'style="display:inline" '
        f'onsubmit="return confirm(\'Delete this {label}?\')">'
        f'<button type="submit" class="btn btn-danger">Delete</button></form>'
    )


def dashboard(request: Request) -> HTMLResponse:
    db = _db_path()
    body_parts: list[str] = []

    if not db.exists():
        body_parts.append('<div class="card"><p>No database found. Start using myMem0ry by saving memories.</p></div>')
        return HTMLResponse(_layout("Dashboard", "\n".join(body_parts)))

    conn = get_connection(db)
    init_schema(conn)

    total = conn.execute("SELECT count(*) FROM memories WHERE deleted_at IS NULL").fetchone()[0]
    projects = conn.execute(
        "SELECT project_id, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL AND deleted_at IS NULL "
        "GROUP BY project_id ORDER BY cnt DESC LIMIT 10"
    ).fetchall()

    by_scope = conn.execute(
        "SELECT scope, count(*) as cnt FROM memories WHERE deleted_at IS NULL GROUP BY scope"
    ).fetchall()
    by_type = conn.execute(
        "SELECT memory_type, count(*) as cnt FROM memories WHERE deleted_at IS NULL GROUP BY memory_type"
    ).fetchall()

    recent = conn.execute(
        "SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    handoffs_open = conn.execute(
        "SELECT count(*) FROM handoffs WHERE status = 'open'"
    ).fetchone()[0]

    version_row = conn.execute(
        "SELECT value FROM schema_meta WHERE key='version'"
    ).fetchone()
    conn.close()

    schema_ver = version_row["value"] if version_row else "?"

    stats_html = f"""<div class="stats">
  <div class="stat"><div class="num">{total}</div><div class="lbl">memories</div></div>
  <div class="stat"><div class="num">{len(projects)}</div><div class="lbl">projects</div></div>
  <div class="stat"><div class="num"><a href="/handoffs?status=open" style="color:inherit">{handoffs_open}</a></div><div class="lbl">open handoffs</div></div>
  <div class="stat"><div class="num">v{schema_ver}</div><div class="lbl">schema</div></div>
</div>"""

    scopes_html = " ".join(
        _tag(row["scope"], f'{row["scope"]} ({row["cnt"]})') for row in by_scope
    )
    types_html = " ".join(
        _tag(row["memory_type"], f'{row["memory_type"]} ({row["cnt"]})') for row in by_type
    )

    cards_html = "".join(_memory_card(dict(r)) for r in recent)

    body_parts.append(stats_html)
    body_parts.append(f'<h2>Scopes</h2><div>{scopes_html}</div>')
    body_parts.append(f'<h2>Types</h2><div>{types_html}</div>')
    body_parts.append(f'<h2>Recent Memories</h2>{cards_html}')

    return HTMLResponse(_layout("Dashboard", "\n".join(body_parts)))


def projects_page(request: Request) -> HTMLResponse:
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout("Projects", _NO_DB, "projects"))

    conn = get_connection(db)
    init_schema(conn)

    mem_projects: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        "SELECT project_id, project_path, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL AND deleted_at IS NULL "
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
        "SELECT count(*) FROM memories WHERE scope='global' AND deleted_at IS NULL"
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
  <td>{p['obs_cnt']}</td>
</tr>"""
        for p in sorted_projects
    )

    body = f"""<h2>Global Memories</h2>
<div class="card"><a href="/project/global">{global_cnt} global memories</a></div>
<h2>Projects</h2>
<table><tr><th>Project ID</th><th>Path</th><th>Memories</th><th>Observations</th></tr>
{rows_html}</table>"""

    return HTMLResponse(_layout("Projects", body, "projects"))


def project_detail(request: Request) -> HTMLResponse:
    pid = request.path_params["project_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Project", _NO_DB))

    conn = get_connection(db)
    init_schema(conn)

    if pid == "global":
        rows = conn.execute(
            "SELECT * FROM memories WHERE scope='global' AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE project_id=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 100",
            (pid,),
        ).fetchall()

    by_scope = conn.execute(
        "SELECT scope, count(*) as cnt FROM memories WHERE project_id=? AND deleted_at IS NULL GROUP BY scope",
        (pid,),
    ).fetchall() if pid != "global" else []

    conn.close()

    scope_html = " ".join(
        _tag(r["scope"], f'{r["scope"]} ({r["cnt"]})') for r in by_scope
    )

    cards_html = "".join(_memory_card(dict(r)) for r in rows)

    body = f"""<h2>{_esc(pid)}</h2>
<div>{scope_html}</div>
<h2>Memories ({len(rows)})</h2>
{cards_html if cards_html else '<div class="card meta">No memories found.</div>'}"""

    return HTMLResponse(_layout(f"Project: {pid}", body))


def memory_detail(request: Request) -> HTMLResponse:
    mid = request.path_params["memory_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Memory", _NO_DB))

    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(_layout("Memory", f'<div class="card"><p>Memory {mid} not found.</p></div>'))

    m = dict(row)

    tags: list[str] = json.loads(m.get("tags") or "[]")
    tags_html = " ".join(_tag("log", t) for t in tags)

    content = _esc(m["content"])

    body = f"""<div class="card">
  <h2>{_esc(m.get('title') or m['id'])}</h2>
  <div>{_tag(m['scope'], m['scope'])} {_tag(m.get('memory_type','log'), m.get('memory_type','log'))}
  {(' <span class="meta pinned">pinned</span>' if m.get('pinned') else '')}</div>
  <div class="meta">
    Created: {(m.get('created_at') or '')[:19]} &middot;
    Updated: {(m.get('updated_at') or 'never')[:19]} &middot;
    Source: {m.get('source','')} &middot;
    Access: {m.get('access_count',0)}x &middot;
    Salience: {m.get('salience',0):.3f}
  </div>
  <div class="meta">Project: {_esc(m.get('project_id'))} &middot; Context: {_esc(m.get('context'))} &middot; Session: {_esc(m.get('session_id'))}</div>
  {f'<div>{tags_html}</div>' if tags else ''}
  <div style="margin-top:.5rem">{_delete_form(mid, 'memory', 'memory')}</div>
</div>
<h3>Content</h3>
<pre>{content}</pre>"""

    return HTMLResponse(_layout(f"Memory: {m.get('title', mid)}", body))


def observation_detail(request: Request) -> HTMLResponse:
    oid = request.path_params["observation_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Observation", _NO_DB))

    conn = get_connection(db)
    init_schema(conn)

    row = conn.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(_layout("Observation", f'<div class="card"><p>Observation {oid} not found.</p></div>'))

    o = dict(row)
    body_text = _esc(o.get("body") or "")
    oid = o["id"]

    body = f"""<div class="card">
  <h2>{_esc(o.get('title') or o['id'])}</h2>
  <div>{_tag(o.get('kind', 'other'), o.get('kind', 'other'))}</div>
  <div class="meta">
    Created: {(o.get('created_at') or '')[:19]} &middot;
    Agent: {_esc(o.get('agent'))} &middot;
    Session: {_esc(o.get('session_id'))}
  </div>
  <div class="meta">Project: {_esc(o.get('project_id'))} &middot; CWD: {_esc(o.get('cwd'))}</div>
  <div style="margin-top:.5rem">{_delete_form(oid, 'observation', 'observation')}</div>
</div>
<h3>Body</h3>
<pre>{body_text if body_text else '<em class="meta">empty</em>'}</pre>"""

    return HTMLResponse(_layout(f"Observation: {o.get('title', oid)}", body))


def search_page(request: Request) -> HTMLResponse:
    q = request.query_params.get("q", "")
    scope = request.query_params.get("scope", "")
    mtype = request.query_params.get("type", "")
    results_html = ""

    if q:
        db = _db_path()
        if db.exists():
            conn = get_connection(db)
            init_schema(conn)

            conditions: list[str] = ["deleted_at IS NULL"]
            params: list[Any] = []

            if scope:
                conditions.append("scope = ?")
                params.append(scope)
            if mtype:
                conditions.append("memory_type = ?")
                params.append(mtype)

            conditions.append("(content LIKE ? OR title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

            where = " AND ".join(conditions)
            sql = f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT 50"
            rows = conn.execute(sql, params).fetchall()
            conn.close()

            results_html = f'<div class="meta">{len(rows)} results</div>' + "".join(
                _memory_card(dict(r)) for r in rows
            )
            if not rows:
                results_html = '<div class="card meta">No results found.</div>'

    scope_options = [("global", "global"), ("project", "project"), ("context", "context"), ("session", "session")]
    type_options = [("fact", "fact"), ("decision", "decision"), ("pattern", "pattern"), ("log", "log")]

    scope_select = "".join(
        f'<option value="{v}" {"selected" if scope==v else ""}>{label}</option>'
        for v, label in scope_options
    )
    type_select = "".join(
        f'<option value="{v}" {"selected" if mtype==v else ""}>{label}</option>'
        for v, label in type_options
    )

    body = f"""<form method="get" action="/search" style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
  <input type="text" name="q" value="{html.escape(q)}" placeholder="Search memories..." autofocus>
  <select name="scope" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.5rem;border-radius:6px">
    <option value="">all scopes</option>{scope_select}
  </select>
  <select name="type" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.5rem;border-radius:6px">
    <option value="">all types</option>{type_select}
  </select>
  <button type="submit" class="btn">Search</button>
</form>
{results_html}"""

    return HTMLResponse(_layout("Search", body, "search"))


def _target_link(row: dict[str, Any]) -> str:
    ttype = row.get("target_type", "")
    tid = row.get("target_id", "")
    if ttype == "observation":
        href = f"/observation/{tid}"
    elif ttype == "handoff":
        href = f"/handoff/{tid}"
    else:
        href = f"/memory/{tid}"
    return f'<a href="{href}">{_esc(tid)}</a>'


def audit_page(request: Request) -> HTMLResponse:
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout(_TITLE_AUDIT, _NO_DB, "audit"))

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
  <td>{_target_link(dict(row))}</td>
  <td class="meta">{_esc(dict(row).get('agent'))}</td>
  <td class="meta" style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{_esc(dict(row).get('details'))}</td>
</tr>"""
        for row in rows
    )

    body = f"""<h2>Audit Log ({len(rows)} entries)</h2>
<table>
<tr><th>Time</th><th>Action</th><th>Type</th><th>Target</th><th>Agent</th><th>Details</th></tr>
{rows_html}
</table>"""

    return HTMLResponse(_layout(_TITLE_AUDIT, body, "audit"))


def api_memories(request: Request) -> JSONResponse:
    db = _db_path()
    if not db.exists():
        return JSONResponse([])

    conn = get_connection(db)
    init_schema(conn)

    q = request.query_params.get("q", "")
    scope = request.query_params.get("scope", "")
    mtype = request.query_params.get("type", "")
    limit = min(int(request.query_params.get("limit", "50")), 200)

    conditions: list[str] = ["deleted_at IS NULL"]
    params: list[Any] = []

    if scope:
        conditions.append("scope = ?")
        params.append(scope)
    if mtype:
        conditions.append("memory_type = ?")
        params.append(mtype)
    if q:
        conditions.append("(content LIKE ? OR title LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = " AND ".join(conditions)
    sql = f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return JSONResponse([dict(r) for r in rows])


def delete_memory_page(request: Request) -> Any:
    from ..db.store import delete_memory

    mid = request.path_params["memory_id"]
    delete_memory(_db_path(), mid)
    return RedirectResponse(url="/", status_code=303)


def delete_observation_page(request: Request) -> Any:
    from ..db.store import delete_observation

    oid = request.path_params["observation_id"]
    delete_observation(_db_path(), oid)
    return RedirectResponse(url="/", status_code=303)


def handoffs_page(request: Request) -> HTMLResponse:
    db = _db_path()
    if not db.exists():
        return HTMLResponse(_layout("Handoffs", _NO_DB, "handoffs"))

    status_filter = request.query_params.get("status", "")

    conn = get_connection(db)
    init_schema(conn)

    if status_filter:
        rows = conn.execute(
            "SELECT * FROM handoffs WHERE status=? ORDER BY created_at DESC LIMIT 100",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM handoffs ORDER BY created_at DESC LIMIT 100"
        ).fetchall()

    counts = {
        r["status"]: r["cnt"]
        for r in conn.execute(
            "SELECT status, count(*) as cnt FROM handoffs GROUP BY status"
        ).fetchall()
    }
    conn.close()

    status_tabs = ""
    for s, label in [("", "All"), ("open", "Open"), ("accepted", "Accepted"), ("expired", "Expired")]:
        active = "active" if status_filter == s else ""
        cnt = counts.get(s, "") if s else sum(counts.values())
        status_tabs += f'<a href="/handoffs{"?status="+s if s else ""}" class="{active}">{label} ({cnt})</a> '

    _STATUS_COLOR = {"open": "green", "accepted": "project", "expired": "log"}

    rows_html = "".join(
        f"""<tr>
  <td><a href="/handoff/{_esc(dict(r)['id'])}">{_esc(dict(r)['id'])}</a></td>
  <td>{_tag(_STATUS_COLOR.get(dict(r)['status'], 'log'), dict(r)['status'])}</td>
  <td class="meta">{_esc(dict(r).get('from_agent'))}</td>
  <td class="meta">{_esc(dict(r).get('project_id'))}</td>
  <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{_esc((dict(r).get('summary') or '')[:120])}</td>
  <td class="meta">{(dict(r).get('created_at') or '')[:16]}</td>
</tr>"""
        for r in rows
    )

    body = f"""<h2>Handoffs</h2>
<div style="margin-bottom:1rem">{status_tabs}</div>
<table>
<tr><th>ID</th><th>Status</th><th>From</th><th>Project</th><th>Summary</th><th>Created</th></tr>
{rows_html if rows_html else '<tr><td colspan="6" class="meta">No handoffs found.</td></tr>'}
</table>"""

    return HTMLResponse(_layout("Handoffs", body, "handoffs"))


def handoff_detail(request: Request) -> HTMLResponse:
    hid = request.path_params["handoff_id"]
    db = _db_path()

    if not db.exists():
        return HTMLResponse(_layout("Handoff", _NO_DB))

    conn = get_connection(db)
    init_schema(conn)
    row = conn.execute("SELECT * FROM handoffs WHERE id=?", (hid,)).fetchone()
    conn.close()

    if not row:
        return HTMLResponse(_layout("Handoff", f'<div class="card"><p>Handoff {hid} not found.</p></div>'))

    ho = dict(row)
    oq: list[str] = json.loads(ho.get("open_questions") or "[]")
    ns: list[str] = json.loads(ho.get("next_steps") or "[]")

    _STATUS_COLOR = {"open": "green", "accepted": "project", "expired": "log"}
    status_tag = _tag(_STATUS_COLOR.get(ho["status"], "log"), ho["status"])

    oq_html = "".join(f"<li>{_esc(q)}</li>" for q in oq) if oq else "<li class='meta'>none</li>"
    ns_html = "".join(f"<li>{_esc(s)}</li>" for s in ns) if ns else "<li class='meta'>none</li>"

    body = f"""<div class="card">
  <h2>Handoff {_esc(hid)}</h2>
  <div>{status_tag}</div>
  <div class="meta" style="margin-top:.5rem">
    From: {_esc(ho.get('from_agent'))} &middot;
    Created: {(ho.get('created_at') or '')[:19]} &middot;
    Expires: {(ho.get('expires_at') or '')[:10]}
  </div>
  <div class="meta">
    Project: {_esc(ho.get('project_id'))} &middot;
    Path: {_esc(ho.get('project_path'))} &middot;
    Session: {_esc(ho.get('session_id'))}
  </div>
  {f'<div class="meta">Accepted by: {_esc(ho.get("accepted_by"))} @ {(ho.get("accepted_at") or "")[:19]}</div>' if ho.get("accepted_by") else ""}
</div>
<h3>Summary</h3>
<pre>{_esc(ho.get('summary') or '')}</pre>
<h3>Open Questions</h3>
<ul style="padding-left:1.5rem">{oq_html}</ul>
<h3>Next Steps</h3>
<ul style="padding-left:1.5rem">{ns_html}</ul>"""

    return HTMLResponse(_layout(f"Handoff: {hid}", body))
