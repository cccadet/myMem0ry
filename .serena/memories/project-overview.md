# myMem0ry — visão geral

Sistema pessoal de memória para agentes de código AI. Python 3.11+, gerenciado com `uv`. Offline, zero API keys, handoffs cross-agent, MCP server, busca semântica via spaCy + sqlite-vec.

## Camadas

- **CLI** (`src/mem0ry/cli/main.py`): Typer app; comandos `search/index/split/migrate/stats/projects/doctor/serve/handoff/hooks/observe`.
- **MCP server** (`src/mem0ry/mcp_server.py`): FastMCP; 12 `@mcp.tool()`; expõe HTTP transport com web UI.
- **HTTP transport**: `/health`, `POST /hook`, `GET /handoff/accept`, web UI montada de `web/__init__.py`.
- **Hooks** (`hooks/<agente>/*.sh` na raiz): bash scripts que `curl POST /hook` (fire-and-forget) e spoolam em falha.
- **DB** (`src/mem0ry/db/`): SQLite + sqlite-vec; tabelas `memories/observations/handoffs/audit_log/schema_meta`; schema v8.
- **Web UI** (`src/mem0ry/web/`): Starlette + Jinja; 25 rotas read-only + 9 POST; dark mode, sem JS framework.

## Entrypoints (pyproject.toml `[project.scripts]`)

- `mymem0ry` → CLI principal
- `mymem0ry-mcp` → servidor FastMCP (stdio ou streamable-http)

## Princípios arquiteturais

- **Sem LLM na escrita**: hooks arquivam conversas e gravam observações sem gastar tokens. MCP tools leem + escrevem seletivo (`save_memory`).
- **Contexto em cascata**: `get_context()` agrega 4 níveis (`session → context → project → global`).
- **Evolução de fatos**: `evolve_fact` consolida fatos contraditórios via `superseded_by` (soft-delete do antigo).
- **Retenção por tier**: `log` 90d, `pattern` 365d, `fact`/`decision` indefinido (auto-pinned).

## When editing…

- Adicionar comando CLI: editar `src/mem0ry/cli/main.py`; novo entrypoint exige atualização de `pyproject.toml`.
- Adicionar tool MCP: `mcp_server.py` com `@mcp.tool()` (decorator obrigatório — sem ele, a tool some); adicionar teste em `tests/test_mcp_server.py`.
- Adicionar rota web: lista de `Route(...)` em `web/__init__.py`; template em `web/templates.py`; string i18n em `web/i18n.py`.
- Adicionar parser: subclasse `BaseParser` em `parsers/base.py`; registrar em `writer.py`; teste em `tests/test_parser_<fonte>.py`.
