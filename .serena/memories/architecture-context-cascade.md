# Cascata de contexto

4 níveis de escopo, agregados em `get_context()` na ordem do mais específico ao mais amplo. Retorna até `top_k` distribuídos pelos níveis.

## Níveis (do mais específico ao mais amplo)

1. **`session`** — vinculado a um `session_id` (de hook ou MCP). Mais efêmero.
2. **`context`** — branch/worktree do git. Genérico: feature, worktree, release.
3. **`project`** — URL do `git remote get-url origin`. Cruza branches do mesmo repo.
4. **`global`** — sem amarração a projeto. Preferências do usuário, regras pessoais.

## Resolução

- **`utils/git_context.py:resolve_project_id(cwd)`** → URL crua do `origin` (ou `None` fora de repo git).
- **`utils/git_context.py:resolve_context(cwd)`** → `git rev-parse --abbrev-ref HEAD`.
- `save_memory` aceita `project_id`/`context`/`session_id` explícitos para override.

## Uso

- **`get_context(cwd, top_k)`** agrega os 4 níveis e devolve memórias distribuídas.
- **`search_memory(cwd, ...)`** filtra por escopo (default = `project` + `global`).
- **`save_memory(scope, ...)`** escolhe o nível; default = `global`.

## Filtros adicionais

- `memory_type` (`fact`/`decision`/`pattern`/`log`).
- `tags` (lista).
- `scope` exato.

## Gotcha

- **Fora de repo git**: `project_id = None`. Memórias `project` são invisíveis, mas `global` continua funcionando.
- **`superseded_by` setado**: `get_context()` e `search_memory()` **excluem** o registro. Evolução é invisível para leitura.

## When editing…

- `get_context()`: `src/mem0ry/db/store.py` (provavelmente) + `src/mem0ry/mcp_server.py` (registro MCP).
- Adicionar nível novo (raro): repensar a cascata — quebra o contrato de "do mais específico ao mais amplo".
- Adicionar campo de filtro em `search_memory`: o tool MCP e a função de store devem ser atualizados em par.
- Mexer em `resolve_project_id`/`resolve_context`: validar com `mymem0ry projects` e `mymem0ry stats`.
