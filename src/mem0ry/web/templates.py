from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .i18n import t


_TITLE_AUDIT = "Audit Log"
_NO_DB = '<div class="card"><p>No database found.</p></div>'


def _db_path() -> Path:
    from ..config import MemoryConfig

    return Path(MemoryConfig().db_path)


def _css() -> str:
    return """
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0b0f16;--bg-grid:rgba(255,255,255,.018);
  --elev:#11161f;--surface:#151b25;--surface-2:#1b222e;
  --border:#262d39;--border-strong:#39414e;
  --text:#e9eef5;--text-2:#9aa4b3;--text2:#9aa4b3;--text-3:#7a8290;
  --accent:#58a6ff;--accent-soft:rgba(88,166,255,.13);--accent-line:rgba(88,166,255,.35);
  --green:#3fb950;--green-soft:rgba(63,185,80,.13);
  --yellow:#d29922;--red:#f85149;--red-soft:rgba(248,81,73,.12);
  --purple:#bc8cff;--cyan:#79c0ff;--cyan-soft:rgba(121,192,255,.13);
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.55);
  --shadow-lift:0 2px 4px rgba(0,0,0,.4),0 18px 40px -18px rgba(0,0,0,.7);
  --mono:ui-monospace,"SF Mono","JetBrains Mono","Cascadia Code",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
}
html[data-theme="light"]{
  --bg:#fbfcfe;--bg-grid:rgba(0,0,0,.022);
  --elev:#ffffff;--surface:#f4f7fb;--surface-2:#eef2f7;
  --border:#dde3ec;--border-strong:#c3ccd8;
  --text:#1a1f29;--text-2:#56606e;--text2:#56606e;--text-3:#6b7280;
  --accent:#0a6ed1;--accent-soft:rgba(10,110,209,.10);--accent-line:rgba(10,110,209,.30);
  --green:#1a7f37;--green-soft:rgba(26,127,55,.12);
  --yellow:#9a6700;--red:#cf222e;--red-soft:rgba(207,34,46,.10);
  --purple:#8250df;--cyan:#0a6ed1;--cyan-soft:rgba(10,110,209,.10);
  --shadow:0 1px 2px rgba(20,30,50,.06),0 8px 24px -14px rgba(20,30,50,.18);
  --shadow-lift:0 2px 6px rgba(20,30,50,.08),0 18px 40px -20px rgba(20,30,50,.28);
}
body{font-family:var(--sans);background:var(--bg);color:var(--text);line-height:1.55;
  -webkit-font-smoothing:antialiased;min-height:100vh;
  background-image:
    radial-gradient(900px 500px at 88% -8%,var(--accent-soft),transparent 70%),
    linear-gradient(var(--bg-grid) 1px,transparent 1px),
    linear-gradient(90deg,var(--bg-grid) 1px,transparent 1px);
  background-size:auto,34px 34px,34px 34px}
.wrap{max-width:1180px;margin:0 auto;padding:0 1.5rem 7rem}
a{color:var(--accent);text-decoration:none;transition:color .15s}
a:hover{text-decoration:none;color:color-mix(in srgb,var(--accent) 80%,var(--text))}
h1{font-size:1.6rem;font-weight:700;margin-bottom:1.2rem;letter-spacing:-.02em}
h2{font-size:1.25rem;font-weight:600;margin:2rem 0 .8rem;letter-spacing:-.01em;color:var(--text)}
h3{font-size:.75rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3);
  font-family:var(--mono);margin:1.5rem 0 .6rem}

/* focus states for accessibility */
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{
  outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}

/* header */
header{position:sticky;top:0;z-index:50;
  background:color-mix(in srgb,var(--bg) 82%,transparent);
  backdrop-filter:saturate(140%) blur(10px);border-bottom:1px solid var(--border)}
.head-inner{max-width:1180px;margin:0 auto;padding:.85rem 1.5rem .6rem;
  display:flex;flex-direction:column;gap:.6rem}
.brand-row{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.brand{font-family:var(--mono);font-size:1.3rem;font-weight:700;letter-spacing:-.02em;
  color:var(--text);display:inline-flex;align-items:baseline}
.brand b{color:var(--accent);font-weight:700}
.brand .dot{width:7px;height:7px;border-radius:50%;background:var(--green);display:inline-block;
  margin-left:.55rem;box-shadow:0 0 0 3px var(--green-soft);animation:pulse 2.6s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
nav{display:flex;gap:.15rem;flex-wrap:wrap;margin:0 -.4rem}
nav a{position:relative;padding:.4rem .7rem;border-radius:7px;color:var(--text-2);font-size:.9rem;transition:.15s}
nav a:hover{color:var(--text);background:var(--surface)}
nav a.active{color:var(--text)}
nav a.active::after{content:"";position:absolute;left:.7rem;right:.7rem;bottom:-.62rem;height:2px;
  background:var(--accent);border-radius:2px 2px 0 0}

/* prefs */
.prefs{display:flex;gap:.5rem;align-items:center}
.prefs .seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:var(--surface)}
.prefs .seg a{padding:.3rem .6rem;color:var(--text-2);cursor:pointer;font-size:.78rem;font-family:var(--mono);transition:.15s}
.prefs .seg a:hover{color:var(--text);background:var(--surface-2)}
.prefs .seg a.active{background:var(--accent-soft);color:var(--accent)}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:34px;height:30px;
  border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text-2);cursor:pointer;transition:.15s;font-size:.9rem}
.icon-btn:hover{color:var(--text);border-color:var(--border-strong)}

/* reveal */
.reveal{opacity:0;transform:translateY(8px);animation:rise .5s cubic-bezier(.22,.61,.36,1) forwards}
@keyframes rise{to{opacity:1;transform:none}}

/* generic card */
.card{background:var(--elev);border:1px solid var(--border);border-radius:12px;padding:1rem 1.15rem;
  margin:.6rem 0;box-shadow:var(--shadow);transition:border-color .2s,box-shadow .2s}
.card:hover{border-color:var(--border-strong)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}

/* resume band */
.resume{margin-top:1.6rem;border:1px solid var(--border);border-radius:14px;
  background:linear-gradient(180deg,var(--accent-soft),transparent 60%),var(--elev);
  box-shadow:var(--shadow);overflow:hidden}
.resume-head{display:flex;align-items:center;gap:.6rem;padding:.95rem 1.15rem .35rem;flex-wrap:wrap}
.resume-head .k{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3);font-family:var(--mono)}
.resume-head h2{font-size:1.1rem;font-weight:700;color:var(--text);letter-spacing:-.01em;margin:0}
.resume-head .grow{flex:1}
.resume-head .all{font-size:.84rem;color:var(--text-2)}
.resume-head .all:hover{color:var(--accent)}
.pill{font-family:var(--mono);font-size:.74rem;font-weight:600;padding:.12rem .5rem;border-radius:20px;
  background:var(--accent-soft);color:var(--accent);border:1px solid var(--accent-line)}
.resume-list{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;padding:.45rem 1.15rem 1.15rem}
.ho{display:block;padding:.8rem .9rem;border:1px solid var(--border);border-radius:10px;
  background:var(--surface);transition:.18s;min-width:0}
.ho:hover{border-color:var(--accent-line);transform:translateY(-2px);box-shadow:var(--shadow-lift)}
.ho .top{display:flex;align-items:center;gap:.5rem;margin-bottom:.35rem}
.ho .repo{font-family:var(--mono);font-size:.74rem;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.ho .ago{font-family:var(--mono);font-size:.72rem;color:var(--text-3);white-space:nowrap}
.ho .sum{color:var(--text);font-size:.92rem;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.dotmark{width:7px;height:7px;border-radius:50%;background:var(--green);flex-shrink:0}

/* stats */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem;margin-top:1.4rem}
.stat{position:relative;background:var(--elev);border:1px solid var(--border);border-radius:12px;
  padding:.9rem 1rem;box-shadow:var(--shadow);transition:.18s;overflow:hidden}
.stat:hover{border-color:var(--border-strong);transform:translateY(-1px)}
.stat .num{font-family:var(--mono);font-size:2rem;font-weight:700;line-height:1;color:var(--text);letter-spacing:-.03em}
.stat .lbl{font-size:.78rem;color:var(--text-2);margin-top:.35rem}
.stat.is-accent{border-color:var(--accent-line);background:linear-gradient(180deg,var(--accent-soft),transparent 55%),var(--elev)}
.stat.is-accent .num{color:var(--accent)}
.stat.is-muted .num{color:var(--text-3)}
.stat a{color:inherit}
.schema-chip{display:inline-flex;align-items:center;gap:.4rem;margin-top:1rem;font-family:var(--mono);font-size:.72rem;color:var(--text-3)}
.schema-chip b{color:var(--text-2)}

/* composition */
.comp{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem;margin-top:1.5rem;
  background:var(--elev);border:1px solid var(--border);border-radius:12px;padding:1.1rem 1.2rem;box-shadow:var(--shadow)}
.comp-block .ttl{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3);font-family:var(--mono);margin-bottom:.55rem}
.bar{display:flex;height:9px;border-radius:6px;overflow:hidden;background:var(--surface-2);margin-bottom:.6rem}
.bar i{display:block;height:100%;transition:width .3s ease}
.legend{display:flex;gap:1rem;flex-wrap:wrap}
.legend span{display:inline-flex;align-items:center;gap:.4rem;font-size:.82rem;color:var(--text-2)}
.legend .sw{width:9px;height:9px;border-radius:3px}
.legend b{color:var(--text);font-family:var(--mono);font-size:.8rem}
.c-global{background:var(--accent)} .c-project{background:var(--green)}
.c-context{background:var(--yellow)} .c-session{background:var(--purple)}
.c-decision{background:var(--red)} .c-fact{background:var(--cyan)} .c-pattern{background:var(--green)} .c-log{background:var(--text-3)}

/* section header */
.sec{display:flex;align-items:center;gap:.8rem;margin:2.5rem 0 1rem}
.sec h2{margin:0;font-size:1.25rem}
.sec .grow{flex:1}
.minifilter{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:var(--surface)}
.minifilter a{padding:.28rem .65rem;font-size:.8rem;color:var(--text-2);cursor:pointer;transition:.15s}
.minifilter a.active{background:var(--accent-soft);color:var(--accent)}
.minifilter a:hover{color:var(--text)}

/* memory cards */
.mem{position:relative;display:flex;gap:0;background:var(--elev);border:1px solid var(--border);
  border-radius:12px;margin-bottom:.7rem;box-shadow:var(--shadow);overflow:hidden;
  transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease}
.mem:hover{transform:translateY(-3px);border-color:var(--accent-line);
  box-shadow:0 4px 12px rgba(0,0,0,.15),0 12px 28px -12px rgba(0,0,0,.4)}
.mem .rail{width:4px;flex-shrink:0;align-self:stretch;background:var(--text-3)}
.rail.t-decision{background:var(--red)} .rail.t-fact{background:var(--cyan)}
.rail.t-pattern{background:var(--green)} .rail.t-log{background:var(--text-3)}
.mem .body{flex:1;min-width:0;padding:.95rem 1.1rem .9rem}
.mem.pinned{border-color:var(--accent-line)}
.mem.pinned::before{content:"";position:absolute;inset:0;border-radius:12px;pointer-events:none;box-shadow:inset 0 0 0 1px var(--accent-line)}
.mhead{display:flex;align-items:flex-start;gap:.55rem}
.mem-checkbox{margin-top:.28rem;accent-color:var(--accent);flex-shrink:0;cursor:pointer}
.mtitle{font-weight:650;font-size:1.02rem;color:var(--text);line-height:1.35;letter-spacing:-.01em}
.mtitle:hover{color:var(--accent)}
.mhead .grow{flex:1;min-width:0}
.chips{display:flex;gap:.35rem;flex-shrink:0;align-items:center;margin-top:.12rem;flex-wrap:wrap}
.pin{margin-left:.15rem;color:var(--accent);font-size:.82rem}
.recall{color:var(--text-2)}
.recall b{color:var(--text);font-weight:600}
.snippet{color:var(--text-2);font-size:.9rem;line-height:1.5;margin:.5rem 0 .6rem;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.snippet code{font-family:var(--mono);font-size:.84em;background:var(--surface-2);padding:.05rem .3rem;border-radius:4px;color:var(--text)}
.ftags{display:flex;gap:.35rem;flex-wrap:wrap}
.ftag{font-family:var(--mono);font-size:.72rem;color:var(--text-3);padding:.1rem .45rem;border-radius:6px;
  background:var(--surface);border:1px solid var(--border);cursor:pointer;transition:.15s}
.ftag::before{content:"#";opacity:.5}
.ftag:hover{color:var(--accent);border-color:var(--accent-line);text-decoration:none}

/* tags */
.tag{font-family:var(--mono);display:inline-flex;align-items:center;padding:.08rem .5rem;border-radius:20px;
  font-size:.72rem;font-weight:600;border:1px solid transparent;white-space:nowrap;margin-right:.3rem}
.tag-global{background:var(--accent-soft);color:var(--accent);border-color:var(--accent-line)}
.tag-project{background:var(--green-soft);color:var(--green);border-color:color-mix(in srgb,var(--green) 35%,transparent)}
.tag-context{background:rgba(210,153,34,.13);color:var(--yellow);border-color:color-mix(in srgb,var(--yellow) 35%,transparent)}
.tag-session{background:rgba(188,140,255,.13);color:var(--purple);border-color:color-mix(in srgb,var(--purple) 35%,transparent)}
.tag-fact{background:var(--cyan-soft);color:var(--cyan);border-color:color-mix(in srgb,var(--cyan) 32%,transparent)}
.tag-decision{background:var(--red-soft);color:var(--red);border-color:color-mix(in srgb,var(--red) 32%,transparent)}
.tag-pattern{background:var(--green-soft);color:var(--green);border-color:color-mix(in srgb,var(--green) 32%,transparent)}
.tag-log{background:var(--surface);color:var(--text-2);border-color:var(--border)}
.tag-green{background:var(--green-soft);color:var(--green);border-color:color-mix(in srgb,var(--green) 32%,transparent)}
.tag-muted{background:var(--surface);color:var(--text-3);border-color:var(--border)}
.tag-superseded{background:var(--red-soft);color:var(--red);border-color:color-mix(in srgb,var(--red) 32%,transparent)}
.tag-clickable{cursor:pointer}
.tag-clickable:hover{text-decoration:none;opacity:.85}

/* code / inputs / tables */
pre{background:var(--elev);border:1px solid var(--border);border-radius:10px;padding:1rem;
  overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;font-size:.85rem;font-family:var(--mono);box-shadow:var(--shadow)}
input[type=text]{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:.5rem .9rem;color:var(--text);font-size:.95rem;width:100%;max-width:500px;transition:border-color .15s,box-shadow .15s}
input[type=text]:focus,textarea:focus,select:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.btn{background:var(--accent);color:#fff;border:1px solid transparent;padding:.42rem 1rem;border-radius:8px;
  cursor:pointer;font-size:.88rem;font-weight:600;font-family:inherit;transition:.15s}
.btn:hover{opacity:.9;transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.btn-danger{background:transparent;border:1px solid color-mix(in srgb,var(--red) 40%,transparent);color:var(--red);
  padding:.42rem 1rem;border-radius:8px;cursor:pointer;font-size:.88rem;font-weight:600;font-family:inherit;transition:.15s}
.btn-danger:hover{background:var(--red-soft)}
.btn-export{background:transparent;border:1px solid color-mix(in srgb,var(--green) 40%,transparent);color:var(--green);
  padding:.42rem 1rem;border-radius:8px;cursor:pointer;font-size:.88rem;font-weight:600;font-family:inherit;transition:.15s}
.btn-export:hover{background:var(--green-soft)}
table{width:100%;border-collapse:collapse;margin:.5rem 0;background:var(--elev);border:1px solid var(--border);
  border-radius:12px;overflow:hidden;box-shadow:var(--shadow)}
th,td{text-align:left;padding:.6rem .8rem;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:none}
th{color:var(--text-3);font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
  font-family:var(--mono);background:var(--surface)}
tbody tr{transition:background .15s}
tbody tr:nth-child(even){background:var(--surface)}
tbody tr:hover,table tr:hover{background:var(--surface-2)}
.meta{color:var(--text-2);font-size:.85rem}
.meta.row{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;font-family:var(--mono);font-size:.74rem;color:var(--text-3);margin:.5rem 0}
.meta.row .sep{width:3px;height:3px;border-radius:50%;background:var(--text-3);opacity:.6}
mark{background:var(--yellow);color:#1a1f29;padding:0 .12rem;border-radius:3px}
.salbar{display:inline-block;width:54px;height:5px;background:var(--surface-2);border-radius:3px;
  vertical-align:middle;overflow:hidden;margin-left:.2rem}
.salbar>i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--cyan));transition:width .3s ease}
.sal{display:inline-flex;align-items:center;gap:.4rem;color:var(--text-2)}

/* filters - grid layout */
.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.8rem;align-items:end;
  margin-bottom:1.2rem;background:var(--elev);border:1px solid var(--border);border-radius:12px;padding:1rem 1.1rem;box-shadow:var(--shadow)}
.filters .filter-group{display:flex;flex-direction:column;gap:.3rem}
.filters label{font-size:.75rem;color:var(--text-3);font-family:var(--mono);text-transform:uppercase;letter-spacing:.05em}
.filters select,.filters input[type=date]{background:var(--surface);border:1px solid var(--border);
  color:var(--text);padding:.5rem;border-radius:8px;font-size:.85rem;width:100%;transition:border-color .15s}
.filters input[type=text]{width:100%;max-width:none;min-width:0}
.filters .filter-actions{display:flex;align-items:end;gap:.5rem}
.pager{display:flex;gap:1rem;align-items:center;justify-content:center;margin:1.2rem 0}
textarea{background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);
  font-size:.95rem;padding:.6rem;width:100%;font-family:inherit;transition:border-color .15s,box-shadow .15s}

/* batch bar (floating) */
.batch-bar{position:fixed;bottom:1rem;left:50%;transform:translateX(-50%) translateY(140%);
  background:var(--elev);border:1px solid var(--border-strong);border-radius:12px;padding:.6rem .8rem;
  display:flex;align-items:center;gap:.7rem;z-index:100;box-shadow:var(--shadow-lift);
  transition:transform .25s cubic-bezier(.22,.61,.36,1);flex-wrap:wrap;justify-content:center}
.batch-bar.visible{transform:translateX(-50%) translateY(0)}
.batch-bar .count{font-family:var(--mono);color:var(--accent);font-weight:700}

/* empty state */
.empty-state{text-align:center;padding:3rem 1rem;color:var(--text-2)}
.empty-state-icon{font-size:3rem;color:var(--text-3);margin-bottom:1rem;opacity:.5}
.empty-state-text{font-size:1rem;color:var(--text-2)}

/* skeleton loading */
.skeleton{background:linear-gradient(90deg,var(--surface) 25%,var(--surface-2) 50%,var(--surface) 75%);
  background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:6px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* responsive */
@media(max-width:900px){
  .stats{grid-template-columns:repeat(2,1fr)}
  .comp,.resume-list{grid-template-columns:1fr}
}
@media(max-width:500px){
  .stats{grid-template-columns:1fr}
  .filters{grid-template-columns:1fr}
}
"""


def _batch_bar(lang: str = "pt") -> str:
    return f"""<div id="batch-bar" class="batch-bar">
  <span class="count" id="batch-count">0</span> {t("common.selected", lang)}
  <form method="post" action="/memories/batch-delete" style="display:inline" id="batch-delete-form">
    <button type="submit" class="btn btn-danger" onclick="return confirm('{t("common.confirm_delete_sel", lang)}')">{t("common.delete", lang)}</button>
  </form>
  <form method="post" action="/memories/export" style="display:inline" id="batch-export-form">
    <button type="submit" class="btn btn-export">{t("common.export", lang)}</button>
  </form>
  <button type="button" class="btn" onclick="toggleSelectAll()">{t("common.select_all", lang)}</button>
</div>""" + _BATCH_SCRIPT


_BATCH_SCRIPT = """<script>
function setPref(k,v){document.cookie=k+'='+v+';path=/;max-age=31536000;samesite=lax';location.reload()}
function toggleTheme(){var d=document.documentElement.getAttribute('data-theme')==='light';setPref('theme',d?'dark':'light')}
function updateBar(){
  var c=document.querySelectorAll('.mem-checkbox:checked').length;
  var bar=document.getElementById('batch-bar');
  var cnt=document.getElementById('batch-count');
  cnt.textContent=c;
  bar.className='batch-bar'+(c>0?' visible':'');
  document.querySelectorAll('.batch-hidden-id').forEach(function(i){i.remove()});
  var df=document.getElementById('batch-delete-form');
  var ef=document.getElementById('batch-export-form');
  document.querySelectorAll('.mem-checkbox:checked').forEach(function(cb){
    [df,ef].forEach(function(f){
      var inp=document.createElement('input');
      inp.type='hidden';inp.name='ids';inp.value=cb.value;
      inp.className='batch-hidden-id';
      f.appendChild(inp);
    });
  });
}
function toggleSelectAll(){
  var all=document.querySelectorAll('.mem-checkbox');
  var checked=document.querySelectorAll('.mem-checkbox:checked');
  var state=checked.length<all.length;
  all.forEach(function(cb){cb.checked=state});
  updateBar();
}
document.addEventListener('change',function(e){
  if(e.target.classList.contains('mem-checkbox'))updateBar();
});
</script>"""


def _prefs_controls(lang: str, theme: str) -> str:
    theme_icon = "☀" if theme == "light" else "☾"
    pt_active = "active" if lang == "pt" else ""
    en_active = "active" if lang == "en" else ""
    return f"""<div class="prefs">
  <span class="seg" role="group" aria-label="{t('common.lang', lang)}">
    <a class="{pt_active}" onclick="setPref('lang','pt')">PT</a>
    <a class="{en_active}" onclick="setPref('lang','en')">EN</a>
  </span>
  <button class="icon-btn" onclick="toggleTheme()" aria-label="{t('common.theme', lang)}" title="{t('common.theme', lang)}">{theme_icon}</button>
</div>"""


def _layout(
    title: str,
    body: str,
    nav_active: str = "dashboard",
    lang: str = "pt",
    theme: str = "dark",
) -> str:
    nav_items = [
        ("dashboard", "/", t("nav.dashboard", lang)),
        ("projects", "/projects", t("nav.projects", lang)),
        ("handoffs", "/handoffs", t("nav.handoffs", lang)),
        ("search", "/search", t("nav.search", lang)),
        ("export", "/export", t("nav.export", lang)),
        ("import-page", "/import", t("nav.import", lang)),
        ("trash", "/trash", t("nav.trash", lang)),
        ("audit", "/audit", t("nav.audit", lang)),
    ]
    nav = "".join(
        f'<a href="{href}" class="{"active" if key == nav_active else ""}">{label}</a>'
        for key, href, label in nav_items
    )
    theme_attr = f' data-theme="{theme}"' if theme == "light" else ""
    return f"""<!DOCTYPE html>
<html lang="{lang}"{theme_attr}><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — myMem0ry</title>
<style>{_css()}</style>
</head><body>
<header>
  <div class="head-inner">
    <div class="brand-row">
      <a href="/" class="brand">myMem<b>0</b>ry<span class="dot" title="server online"></span></a>
      {_prefs_controls(lang, theme)}
    </div>
    <nav>{nav}</nav>
  </div>
</header>
<div class="wrap">
{body}
</div>
{_batch_bar(lang)}
</body></html>"""


def _tag(cls: str, text: str, href: str | None = None) -> str:
    span = f'<span class="tag tag-{cls}{" tag-clickable" if href else ""}">{html.escape(text)}</span>'
    if href:
        return f'<a href="{html.escape(href)}">{span}</a>'
    return span


def _highlight(text: str, terms: list[str]) -> str:
    """HTML-escape ``text`` then wrap each query term in <mark> (case-insensitive)."""
    escaped = html.escape(text)
    for term in terms:
        if not term:
            continue
        pattern = re.compile(re.escape(html.escape(term)), re.IGNORECASE)
        escaped = pattern.sub(lambda mo: f"<mark>{mo.group(0)}</mark>", escaped)
    return escaped


def _salience_bar(salience: float, lang: str) -> str:
    pct = max(0, min(100, round(salience * 100)))
    label = f"{t('mem.salience', lang)} {salience:.2f}"
    return f'<span class="salbar" title="{label}" aria-label="{label}"><i style="width:{pct}%"></i></span>'


def _esc(s: str | None) -> str:
    return html.escape(s or "")


def _parse_tags(raw: Any) -> list[str]:
    """Tags come back from SQLite as a JSON string; tolerate list or junk."""
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw:
        try:
            val = json.loads(raw)
            return [str(x) for x in val] if isinstance(val, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


_RAIL_TYPES = ("decision", "fact", "pattern", "log")


def _memory_card(
    m: dict[str, Any], lang: str = "pt", terms: list[str] | None = None
) -> str:
    title = _esc(m.get("title") or m["id"])
    scope = m.get("scope", "global")
    mtype = m.get("memory_type", "log")
    rail = mtype if mtype in _RAIL_TYPES else "log"
    pinned = " pinned" if m.get("pinned") else ""
    superseded_by = m.get("superseded_by")
    created = (m.get("created_at") or "")[:10]
    raw_content = m.get("content", "") or ""
    snippet = raw_content[:200]
    content = _highlight(snippet, terms) if terms else _esc(snippet)
    if len(raw_content) > 200:
        content += "…"
    mid = m["id"]

    superseded_badge = ""
    if superseded_by:
        label = f'{t("mem.superseded_by", lang)} {superseded_by}'
        superseded_badge = f' <a href="/memory/{_esc(superseded_by)}">{_tag("superseded", label)}</a>'

    pin_chip = '<span class="pin" title="pinned">📌</span>' if m.get("pinned") else ""

    ftags_html = "".join(
        f'<a class="ftag" href="/search?tags={html.escape(tg)}">{html.escape(tg)}</a>'
        for tg in _parse_tags(m.get("tags"))
    )
    ftags_block = f'<div class="ftags">{ftags_html}</div>' if ftags_html else ""

    access = m.get("access_count", 0) or 0
    salience = m.get("salience")
    sal_html = (
        f'<span class="sal">{t("mem.salience", lang)} {_salience_bar(float(salience), lang)}</span>'
        if salience is not None
        else ""
    )

    return f"""<article class="mem{pinned} reveal">
  <span class="rail t-{rail}"></span>
  <div class="body">
    <div class="mhead">
      <input type="checkbox" class="mem-checkbox" value="{mid}" aria-label="Select memory {mid}">
      <span class="grow"><a class="mtitle" href="/memory/{mid}">{title}</a></span>
      <span class="chips">{_tag(scope, scope)}{_tag(mtype, mtype)}{pin_chip}{superseded_badge}</span>
    </div>
    <div class="meta row">
      <span>{created}</span><span class="sep"></span>
      <span>{_esc(m.get('source',''))}</span><span class="sep"></span>
      <span class="recall">↺ {t("mem.accessed", lang)} <b>{access}{t("mem.times", lang)}</b></span>
      {sal_html}
    </div>
    <div class="snippet">{content}</div>
    {ftags_block}
  </div>
</article>"""
