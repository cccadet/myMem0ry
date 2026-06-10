# Hooks e spool

Hooks ficam **na raiz do repo** (`hooks/<agente>/*.sh`), **não** em `src/`. São bash scripts que `curl POST /hook` no servidor HTTP (fire-and-forget).

## Servidor auto-start

- Quando o MCP server sobe, o HTTP server também sobe.
- Hooks **não precisam** de `mymem0ry serve` separado.

## Fire-and-forget + spool

- Script OpenCode usa `--max-time 0.2` (timeout curto).
- **SessionEnd** de Claude Code corre contra o shutdown — POST pode falhar.
- Solução: hook **dropa o evento como JSON em `MEM0RY_SPOOL_DIR`** (default `<data_dir>/spool`).
- Servidor drena spool no startup e em timer background — ver `mcp_server.py:_drain_spool_once`, `_start_spool_drainer`.
- **Não assumir que POST sempre sucede.** Spool é o caminho de recuperação.

## Runtime file

- `mcp_server.py:write_runtime_file` grava arquivo texto plain: linha 1 = spool dir, linha 2 = URL.
- Hooks bash leem esse arquivo em vez de depender de env — sem coordenação de ambiente.

## session_id

- Hook **deve** passar o `session_id` real (vem do stdin JSON, junto com `cwd` e `transcript_path`).
- **NUNCA fabricar um id por invocação** — `auto_handoff_from_session` agrupa observações por id; id novo a cada call = nada agrupa.

## Sanitização

- `src/mem0ry/hooks/sanitize.py:sanitize_payload()` — strip PII, API keys, truncate.
- **Toda** carga de hook passa por aqui antes de persistir (`hooks/router.py:handle_hook_event`).
- Sanitizar é mais barato que revisar — **não pular**.

## Hooks por agente

- `hooks/claude-code/`: `session-start.sh`, `session-end.sh`, `mymem0ry-hook.sh` (lifecycle completo).
- `hooks/codex/`, `hooks/cursor/`, `hooks/gemini-cli/`: similar.
- `hooks/opencode/`: **só** `mymem0ry-hook.sh` (OpenCode não tem framework nativo de lifecycle). MCP tools (`get_context`, `save_memory`) carregam o trabalho.

## Custo de tokens

- Hooks **não** envolvem LLM — arquivamento, logging, lifecycle são zero-token.
- LLM só roda no agente usando as MCP tools.

## When editing…

- **Novo agente**: criar `hooks/<agente>/` com scripts; documentar session_id/cwd no payload esperado.
- **Bug "POST silencioso"**: verificar spool dir; rodar `mymem0ry serve` foreground pra ver logs.
- **Mexer em `handle_hook_event`**: garantir que `sanitize_payload` é chamado **antes** de `store_observation`.
- **Mudar formato do payload**: atualizar sanitize, runtime file, e scripts de hook em par.
