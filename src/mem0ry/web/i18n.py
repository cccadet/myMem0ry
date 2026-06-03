"""Bilingual (pt-BR / en) UI strings for the myMem0ry web interface.

Language and theme are stored in browser cookies (``lang`` / ``theme``) and set
client-side via a small toggle in the header (see ``templates._BATCH_BAR`` JS),
so handlers only need to *read* the preference — no response-cookie plumbing.
"""

from __future__ import annotations

from typing import Any

LANGS = ("pt", "en")
DEFAULT_LANG = "pt"
THEMES = ("dark", "light")
DEFAULT_THEME = "dark"


STRINGS: dict[str, dict[str, str]] = {
    "pt": {
        # nav
        "nav.dashboard": "Painel",
        "nav.projects": "Projetos",
        "nav.handoffs": "Repasses",
        "nav.search": "Buscar",
        "nav.import": "Importar",
        "nav.audit": "Auditoria",
        "nav.trash": "Lixeira",
        # common
        "common.no_db": "Banco de dados não encontrado.",
        "common.no_db_hint": "Banco de dados não encontrado. Comece a usar o myMem0ry salvando memórias.",
        "common.results": "resultados",
        "common.no_results": "Nenhum resultado encontrado.",
        "common.delete": "Excluir",
        "common.export": "Exportar",
        "common.select_all": "Selecionar tudo",
        "common.selected": "selecionada(s)",
        "common.restore": "Restaurar",
        "common.edit": "Editar",
        "common.save": "Salvar",
        "common.cancel": "Cancelar",
        "common.pin": "Fixar",
        "common.unpin": "Desafixar",
        "common.pinned": "fixada",
        "common.confirm_delete": "Excluir esta memória?",
        "common.confirm_delete_sel": "Excluir as memórias selecionadas?",
        "common.lang": "Idioma",
        "common.theme": "Tema",
        "common.theme_dark": "Escuro",
        "common.theme_light": "Claro",
        "common.back": "← Voltar",
        # card / memory
        "mem.superseded_by": "substituída por",
        "mem.supersedes": "Substitui:",
        "mem.accessed": "acessada",
        "mem.times": "x",
        "mem.created": "Criada",
        "mem.updated": "Atualizada",
        "mem.never": "nunca",
        "mem.source": "Fonte",
        "mem.access": "Acessos",
        "mem.salience": "Relevância",
        "mem.project": "Projeto",
        "mem.context": "Contexto",
        "mem.session": "Sessão",
        "mem.content": "Conteúdo",
        "mem.not_found": "Memória {id} não encontrada.",
        # dashboard
        "dash.memories": "memórias",
        "dash.projects": "projetos",
        "dash.open_handoffs": "repasses abertos",
        "dash.evolved_facts": "fatos evoluídos",
        "dash.schema": "schema",
        "dash.scopes": "Escopos",
        "dash.types": "Tipos",
        "dash.scope": "escopo",
        "dash.type": "tipo",
        "dash.recent": "Memórias recentes",
        "dash.resume_k": "retomar",
        "dash.resume_title": "Continue de onde parou",
        "dash.view_all_handoffs": "Ver todos os repasses",
        "dash.store_healthy": "armazenamento saudável",
        "dash.all": "Todas",
        "dash.pinned": "Fixadas",
        "time.just_now": "agora mesmo",
        "time.min_ago": "há {n} min",
        "time.hour_ago": "há {n} h",
        "time.day_ago": "há {n} d",
        # projects
        "proj.global": "Memórias globais",
        "proj.global_count": "{n} memórias globais",
        "proj.projects": "Projetos",
        "proj.col_id": "ID do projeto",
        "proj.col_path": "Caminho",
        "proj.col_mem": "Memórias",
        "proj.col_obs": "Observações",
        "proj.export": "Exportar projeto",
        "proj.memories_n": "Memórias ({n})",
        "proj.no_memories": "Nenhuma memória encontrada.",
        # search
        "search.placeholder": "Buscar memórias...",
        "search.all_scopes": "todos os escopos",
        "search.all_types": "todos os tipos",
        "search.all_sources": "todas as fontes",
        "search.tags_placeholder": "tags (vírgula)",
        "search.date_from": "De",
        "search.date_to": "Até",
        "search.only_pinned": "só fixadas",
        "search.sort": "Ordenar",
        "search.sort.recent": "mais recentes",
        "search.sort.oldest": "mais antigas",
        "search.sort.salience": "relevância",
        "search.sort.access": "mais acessadas",
        "search.sort.title": "título A–Z",
        "search.button": "Buscar",
        "search.prev": "← Anterior",
        "search.next": "Próxima →",
        # handoffs
        "ho.title": "Repasses",
        "ho.all": "Todos",
        "ho.open": "Abertos",
        "ho.accepted": "Aceitos",
        "ho.expired": "Expirados",
        "ho.col_id": "ID",
        "ho.col_status": "Status",
        "ho.col_from": "De",
        "ho.col_project": "Projeto",
        "ho.col_summary": "Resumo",
        "ho.col_created": "Criado",
        "ho.none": "Nenhum repasse encontrado.",
        "ho.from": "De",
        "ho.created": "Criado",
        "ho.expires": "Expira",
        "ho.project": "Projeto",
        "ho.path": "Caminho",
        "ho.session": "Sessão",
        "ho.accepted_by": "Aceito por",
        "ho.summary": "Resumo",
        "ho.open_questions": "Perguntas em aberto",
        "ho.next_steps": "Próximos passos",
        "ho.none_item": "nenhum",
        "ho.not_found": "Repasse {id} não encontrado.",
        "ho.close": "Fechar",
        "ho.confirm_close": "Fechar este repasse?",
        "ho.confirm_delete": "Excluir este repasse permanentemente?",
        # observation
        "obs.agent": "Agente",
        "obs.session": "Sessão",
        "obs.project": "Projeto",
        "obs.cwd": "Diretório",
        "obs.body": "Corpo",
        "obs.empty": "vazio",
        "obs.not_found": "Observação {id} não encontrada.",
        "obs.confirm_delete": "Excluir esta observação?",
        "obs.project_obs": "Observações",
        "obs.none_for_project": "Nenhuma observação neste projeto.",
        "obs.col_id": "ID",
        "obs.col_title": "Título",
        "obs.col_kind": "Tipo",
        "obs.col_agent": "Agente",
        "obs.col_created": "Criada",
        # audit
        "audit.title": "Registro de auditoria",
        "audit.entries": "{n} registros",
        "audit.time": "Hora",
        "audit.action": "Ação",
        "audit.type": "Tipo",
        "audit.target": "Alvo",
        "audit.agent": "Agente",
        "audit.details": "Detalhes",
        # import
        "imp.title": "Importar memórias",
        "imp.select_file": "Selecione o arquivo de exportação (.json):",
        "imp.override": "Sobrescrever ID do projeto (opcional):",
        "imp.button": "Importar",
        "imp.help": "Importe um arquivo JSON exportado anteriormente. Memórias duplicadas (mesmo ID) serão ignoradas.",
        "imp.no_file": "Nenhum arquivo enviado",
        "imp.invalid_json": "JSON inválido: {err}",
        "imp.result": "Importadas: {mem} memórias, {ho} repasses. Ignoradas (duplicadas): {mem_skip} memórias, {ho_skip} repasses.",
        # trash
        "trash.title": "Lixeira",
        "trash.subtitle": "Memórias excluídas ({n})",
        "trash.deleted_at": "Excluída em",
        "trash.grace_until": "Remoção definitiva em",
        "trash.no_grace": "sem prazo definido",
        "trash.empty": "A lixeira está vazia.",
        "trash.hint": "Memórias excluídas podem ser restauradas até a remoção definitiva.",
        "trash.confirm_restore": "Restaurar esta memória?",
        # edit
        "edit.title": "Editar memória",
        "edit.title_label": "Título:",
        "edit.content_label": "Conteúdo:",
        "edit.tags_label": "Tags (separadas por vírgula):",
    },
    "en": {
        # nav
        "nav.dashboard": "Dashboard",
        "nav.projects": "Projects",
        "nav.handoffs": "Handoffs",
        "nav.search": "Search",
        "nav.import": "Import",
        "nav.audit": "Audit Log",
        "nav.trash": "Trash",
        # common
        "common.no_db": "No database found.",
        "common.no_db_hint": "No database found. Start using myMem0ry by saving memories.",
        "common.results": "results",
        "common.no_results": "No results found.",
        "common.delete": "Delete",
        "common.export": "Export",
        "common.select_all": "Select All",
        "common.selected": "selected",
        "common.restore": "Restore",
        "common.edit": "Edit",
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.pin": "Pin",
        "common.unpin": "Unpin",
        "common.pinned": "pinned",
        "common.confirm_delete": "Delete this memory?",
        "common.confirm_delete_sel": "Delete selected memories?",
        "common.lang": "Language",
        "common.theme": "Theme",
        "common.theme_dark": "Dark",
        "common.theme_light": "Light",
        "common.back": "← Back",
        # card / memory
        "mem.superseded_by": "superseded by",
        "mem.supersedes": "Supersedes:",
        "mem.accessed": "accessed",
        "mem.times": "x",
        "mem.created": "Created",
        "mem.updated": "Updated",
        "mem.never": "never",
        "mem.source": "Source",
        "mem.access": "Access",
        "mem.salience": "Salience",
        "mem.project": "Project",
        "mem.context": "Context",
        "mem.session": "Session",
        "mem.content": "Content",
        "mem.not_found": "Memory {id} not found.",
        # dashboard
        "dash.memories": "memories",
        "dash.projects": "projects",
        "dash.open_handoffs": "open handoffs",
        "dash.evolved_facts": "evolved facts",
        "dash.schema": "schema",
        "dash.scopes": "Scopes",
        "dash.types": "Types",
        "dash.scope": "scope",
        "dash.type": "type",
        "dash.recent": "Recent Memories",
        "dash.resume_k": "resume",
        "dash.resume_title": "Pick up where you left off",
        "dash.view_all_handoffs": "View all handoffs",
        "dash.store_healthy": "store healthy",
        "dash.all": "All",
        "dash.pinned": "Pinned",
        "time.just_now": "just now",
        "time.min_ago": "{n} min ago",
        "time.hour_ago": "{n}h ago",
        "time.day_ago": "{n}d ago",
        # projects
        "proj.global": "Global Memories",
        "proj.global_count": "{n} global memories",
        "proj.projects": "Projects",
        "proj.col_id": "Project ID",
        "proj.col_path": "Path",
        "proj.col_mem": "Memories",
        "proj.col_obs": "Observations",
        "proj.export": "Export Project",
        "proj.memories_n": "Memories ({n})",
        "proj.no_memories": "No memories found.",
        # search
        "search.placeholder": "Search memories...",
        "search.all_scopes": "all scopes",
        "search.all_types": "all types",
        "search.all_sources": "all sources",
        "search.tags_placeholder": "tags (comma)",
        "search.date_from": "From",
        "search.date_to": "To",
        "search.only_pinned": "pinned only",
        "search.sort": "Sort",
        "search.sort.recent": "newest",
        "search.sort.oldest": "oldest",
        "search.sort.salience": "salience",
        "search.sort.access": "most accessed",
        "search.sort.title": "title A–Z",
        "search.button": "Search",
        "search.prev": "← Prev",
        "search.next": "Next →",
        # handoffs
        "ho.title": "Handoffs",
        "ho.all": "All",
        "ho.open": "Open",
        "ho.accepted": "Accepted",
        "ho.expired": "Expired",
        "ho.col_id": "ID",
        "ho.col_status": "Status",
        "ho.col_from": "From",
        "ho.col_project": "Project",
        "ho.col_summary": "Summary",
        "ho.col_created": "Created",
        "ho.none": "No handoffs found.",
        "ho.from": "From",
        "ho.created": "Created",
        "ho.expires": "Expires",
        "ho.project": "Project",
        "ho.path": "Path",
        "ho.session": "Session",
        "ho.accepted_by": "Accepted by",
        "ho.summary": "Summary",
        "ho.open_questions": "Open Questions",
        "ho.next_steps": "Next Steps",
        "ho.none_item": "none",
        "ho.not_found": "Handoff {id} not found.",
        "ho.close": "Close",
        "ho.confirm_close": "Close this handoff?",
        "ho.confirm_delete": "Delete this handoff permanently?",
        # observation
        "obs.agent": "Agent",
        "obs.session": "Session",
        "obs.project": "Project",
        "obs.cwd": "CWD",
        "obs.body": "Body",
        "obs.empty": "empty",
        "obs.not_found": "Observation {id} not found.",
        "obs.confirm_delete": "Delete this observation?",
        "obs.project_obs": "Observations",
        "obs.none_for_project": "No observations in this project.",
        "obs.col_id": "ID",
        "obs.col_title": "Title",
        "obs.col_kind": "Kind",
        "obs.col_agent": "Agent",
        "obs.col_created": "Created",
        # audit
        "audit.title": "Audit Log",
        "audit.entries": "{n} entries",
        "audit.time": "Time",
        "audit.action": "Action",
        "audit.type": "Type",
        "audit.target": "Target",
        "audit.agent": "Agent",
        "audit.details": "Details",
        # import
        "imp.title": "Import Memories",
        "imp.select_file": "Select export file (.json):",
        "imp.override": "Override project ID (optional):",
        "imp.button": "Import",
        "imp.help": "Import a previously exported JSON file. Duplicate memories (same ID) will be skipped.",
        "imp.no_file": "No file provided",
        "imp.invalid_json": "Invalid JSON: {err}",
        "imp.result": "Imported: {mem} memories, {ho} handoffs. Skipped (duplicates): {mem_skip} memories, {ho_skip} handoffs.",
        # trash
        "trash.title": "Trash",
        "trash.subtitle": "Deleted memories ({n})",
        "trash.deleted_at": "Deleted at",
        "trash.grace_until": "Permanent removal on",
        "trash.no_grace": "no deadline set",
        "trash.empty": "The trash is empty.",
        "trash.hint": "Deleted memories can be restored until permanent removal.",
        "trash.confirm_restore": "Restore this memory?",
        # edit
        "edit.title": "Edit Memory",
        "edit.title_label": "Title:",
        "edit.content_label": "Content:",
        "edit.tags_label": "Tags (comma-separated):",
    },
}


def get_lang(request: Any) -> str:
    """Resolve the UI language from the ``lang`` cookie (default pt)."""
    lang = ""
    try:
        lang = request.cookies.get("lang", "")
    except Exception:
        lang = ""
    return lang if lang in LANGS else DEFAULT_LANG


def get_theme(request: Any) -> str:
    """Resolve the UI theme from the ``theme`` cookie (default dark)."""
    theme = ""
    try:
        theme = request.cookies.get("theme", "")
    except Exception:
        theme = ""
    return theme if theme in THEMES else DEFAULT_THEME


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    """Translate ``key`` for ``lang``, falling back to en then the key itself.

    ``**kwargs`` are applied via ``str.format`` so strings may carry
    placeholders like ``{n}`` or ``{id}``.
    """
    table = STRINGS.get(lang) or STRINGS[DEFAULT_LANG]
    text = table.get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
