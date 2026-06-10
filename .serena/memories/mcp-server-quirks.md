# MCP server — quirks

Servidor FastMCP em `src/mem0ry/mcp_server.py`. 12 tools registradas com `@mcp.tool()`.

## Ferramentas (12)

`save_memory`, `get_context`, `search_memory`, `search_conversations`, `read_memory`, `memory_handoff_begin`, `memory_handoff_accept`, `memory_pin`, `memory_unpin`, `memory_forget_sweep`, `evolve_fact`, `memory_stats`.

## Quirks críticos

- **`@mcp.tool()` é obrigatório**. Decorator removido = tool some do registro silenciosamente. Já mordeu `memory_handoff_begin`.
- **`tests/test_mcp_server.py`** guarda o registro. Adicionar tool nova → adicionar teste de registro.
- **Globais de módulo** (`_session_id`, `_expander`) inicializam lazy; **não são thread-safe**. Servidor assume 1 cliente MCP.
- **Hook-vs-MCP divisão**: bulk writes (arquivamento de conversa, logging, lifecycle) são **hook-only** para não gastar tokens de LLM. MCP tools são leituras + escritas seletivas (`save_memory` para fatos/decisões).

## HTTP transport (streamable-http)

Endpoints expostos:
- `GET /health` — health check.
- `POST /hook` — recebe eventos de hooks.
- `GET /handoff/accept` — peek de handoff pendente (não-destrutivo).
- Web UI: montada de `src/mem0ry/web/__init__.py` (25 rotas).

## Auth

- `src/mem0ry/auth.py`: Bearer token (`MEM0RY_TOKEN`), host allowlist (`MEM0RY_ALLOWED_HOSTS`, default `localhost,127.0.0.1` — proteção contra DNS rebinding), CORS (`MEM0RY_CORS_ORIGINS`).
- Aplicada como **Starlette middleware** no HTTP transport.
- `MEM0RY_TOKEN` vazio = sem auth (só dev).

## Servidor start

- `mymem0ry serve` foreground; `--detach` background (gerenciado por `daemon.py`).
- Servidor auto-inicia quando o MCP server sobe — hook não precisa de `serve` separado.

## When editing…

- **Nova tool**: adicionar com `@mcp.tool()` em `mcp_server.py`; teste de registro em `tests/test_mcp_server.py`.
- **Bug "tool sumiu"**: grep por `@mcp.tool()` em `mcp_server.py` — se faltar decorator, ferramenta está invisível.
- **Reset entre sessões**: reiniciar o processo (globals não resetam).
- **Mexer em auth**: `auth.py` + variável `MEM0RY_TOKEN` no `.env`. Doc em `docs/`.
- **Mexer em HTTP endpoints**: ver se sobrepõe rota web em `web/__init__.py` (conflito de path trava o starlette).
