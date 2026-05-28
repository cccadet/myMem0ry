"""Read-only web UI for myMem0ry — dark mode, mounted on MCP server."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .config import MemoryConfig
from .db.connection import get_connection
from .db.schema import init_schema

_TITLE_AUDIT = "Audit Log"
_NO_DB = '<div class="card"><p>No database found.</p></div>'


def _db_path() -> Path:
    return Path(MemoryConfig().db_path)


def _css() -> str:
    return """
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--surface:#161b22;--border:#30363d;
  --text:#e6edf3;--text2:#8b949e;--accent:#58a6ff;
  --green:#3fb950;--yellow:#d29922;--red:#f85149;
  --purple:#bc8cff;
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;padding:1rem 2rem;max-width:1200px;margin:0 auto}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
h1{font-size:1.5rem;margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid var(--border)}
h2{font-size:1.2rem;margin:1.5rem 0 .5rem;color:var(--accent)}
h3{font-size:1rem;margin:1rem 0 .3rem;color:var(--purple)}
nav{display:flex;gap:1rem;padding:.5rem 0;margin-bottom:1rem;border-bottom:1px solid var(--border)}
nav a{padding:.3rem .6rem;border-radius:6px;color:var(--text2)}
nav a:hover{background:var(--surface);color:var(--text);text-decoration:none}
nav a.active{background:var(--surface);color:var(--accent)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem;margin:.5rem 0}
.card:hover{border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}
.stats{display:flex;gap:2rem;flex-wrap:wrap;margin:.5rem 0}
.stat{text-align:center}
.stat .num{font-size:2rem;font-weight:700;color:var(--accent)}
.stat .lbl{font-size:.8rem;color:var(--text2)}
.tag{display:inline-block;padding:.1rem .5rem;border-radius:12px;font-size:.75rem;margin-right:.3rem}
.tag-global{background:#1f3a5f;color:var(--accent)}
.tag-project{background:#1a3a2a;color:var(--green)}
.tag-context{background:#3a2a1a;color:var(--yellow)}
.tag-session{background:#2a1a3a;color:var(--purple)}
.tag-fact{background:#1a2a3a;color:#79c0ff}
.tag-decision{background:#2a1a1a;color:var(--red)}
.tag-pattern{background:#1a2a1a;color:var(--green)}
.tag-log{background:#1a1a2a;color:var(--text2)}
pre{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:1rem;
  overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;font-size:.85rem}
input[type=text]{background:var(--surface);border:1px solid var(--border);border-radius:6px;
  padding:.5rem 1rem;color:var(--text);font-size:1rem;width:100%;max-width:500px}
input[type=text]:focus{outline:none;border-color:var(--accent)}
.btn{background:var(--accent);color:var(--bg);border:none;padding:.4rem 1rem;border-radius:6px;
  cursor:pointer;font-size:.9rem}
.btn:hover{opacity:.85}
table{width:100%;border-collapse:collapse;margin:.5rem 0}
th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid var(--border)}
th{color:var(--text2);font-weight:600;font-size:.85rem}
.meta{color:var(--text2);font-size:.85rem}
.pinned::before{content:"\\1F4CC";margin-right:.3rem}
"""


def _layout(title: str, body: str, nav_active: str = "dashboard") -> str:
    nav_items = [
        ("dashboard", "/", "Dashboard"),
        ("projects", "/projects", "Projects"),
        ("search", "/search", "Search"),
        ("audit", "/audit", _TITLE_AUDIT),
    ]
    nav = "".join(
        f'<a href="{href}" class="{"active" if key == nav_active else ""}">{label}</a>'
        for key, href, label in nav_items
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — myMem0ry</title>
<style>{_css()}</style>
</head><body>
<h1><a href="/">myMem0ry</a></h1>
<nav>{nav}</nav>
{body}
</body></html>"""


def _tag(cls: str, text: str) -> str:
    return f'<span class="tag tag-{cls}">{html.escape(text)}</span>'


def _esc(s: str | None) -> str:
    return html.escape(s or "")


def _memory_card(m: dict[str, Any]) -> str:
    title = _esc(m.get("title") or m["id"])
    scope = m.get("scope", "global")
    mtype = m.get("memory_type", "log")
    pinned = " pinned" if m.get("pinned") else ""
    created = (m.get("created_at") or "")[:10]
    content = _esc(m["content"][:200])
    mid = m["id"]
    return f"""<div class="card{pinned}">
  <div><strong><a href="/memory/{mid}">{title}</a></strong>
  {_tag(scope, scope)} {_tag(mtype, mtype)}
  {(' <span class="meta pinned">pinned</span>' if m.get('pinned') else '')}
  </div>
  <div class="meta">{created} &middot; {m.get('source','')} &middot; accessed {m.get('access_count',0)}x</div>
  <div style="margin-top:.3rem">{content}{'...' if len(m.get('content',''))>200 else ''}</div>
</div>"""


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
  <div class="stat"><div class="num">{handoffs_open}</div><div class="lbl">open handoffs</div></div>
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

    projects = conn.execute(
        "SELECT project_id, project_path, count(*) as cnt FROM memories "
        "WHERE project_id IS NOT NULL AND deleted_at IS NULL "
        "GROUP BY project_id ORDER BY cnt DESC"
    ).fetchall()

    global_cnt = conn.execute(
        "SELECT count(*) FROM memories WHERE scope='global' AND deleted_at IS NULL"
    ).fetchone()[0]
    conn.close()

    rows_html = "".join(
        f"""<tr>
  <td><a href="/project/{html.escape(dict(row)['project_id'])}">{_esc(dict(row)['project_id'])}</a></td>
  <td class="meta">{_esc(dict(row).get('project_path'))}</td>
  <td>{row['cnt']}</td>
</tr>"""
        for row in projects
    )

    body = f"""<h2>Global Memories</h2>
<div class="card"><a href="/project/global">{global_cnt} global memories</a></div>
<h2>Projects</h2>
<table><tr><th>Project ID</th><th>Path</th><th>Memories</th></tr>
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
</div>
<h3>Content</h3>
<pre>{content}</pre>"""

    return HTMLResponse(_layout(f"Memory: {m.get('title', mid)}", body))


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
  <td><a href="/memory/{row['target_id']}">{_esc(row['target_id'])}</a></td>
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


def get_web_routes() -> list[Route]:
    return [
        Route("/", dashboard),
        Route("/projects", projects_page),
        Route("/project/{project_id:path}", project_detail),
        Route("/memory/{memory_id}", memory_detail),
        Route("/search", search_page),
        Route("/audit", audit_page),
        Route("/api/memories", api_memories),
    ]
