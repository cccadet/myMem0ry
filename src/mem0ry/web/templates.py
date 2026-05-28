from __future__ import annotations

import html
from pathlib import Path
from typing import Any


_TITLE_AUDIT = "Audit Log"
_NO_DB = '<div class="card"><p>No database found.</p></div>'


def _db_path() -> Path:
    from ..config import MemoryConfig

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
.btn-danger{background:var(--red);color:#fff;border:none;padding:.4rem 1rem;border-radius:6px;
  cursor:pointer;font-size:.9rem}
.btn-danger:hover{opacity:.85}
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
