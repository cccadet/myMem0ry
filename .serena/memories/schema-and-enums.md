# Schema e enums (v8)

> **REGRA DE AUTO-UPDATE**: se `_SCHEMA_VERSION` em `src/mem0ry/db/schema.py:7` mudar, **atualizar esta memória** com a nova versão e tabelas adicionadas. Última verificação: v8.

## Versão atual

- **`_SCHEMA_VERSION = 8`** em `src/mem0ry/db/schema.py:7`.
- Schema init roda todas as migrations em ordem em DB fresco.

## Tabelas (v8)

- `memories` — fatos/decisões/padrões/logs. Tem `superseded_by` (rastreia evolução).
- `observations` — eventos de hook (session-start, post-tool-use, etc.).
- `handoffs` — registros cross-agent.
- `audit_log` — toda mutação (create/delete/import/handoff/evolve).
- `schema_meta` — versão do schema persistida.

## Migrations

- **`src/mem0ry/db/migrate.py`**: cadeia `migrate_v1_to_v2` … `migrate_v7_to_v8`.
- Nova migration: função `migrate_v{N}_to_v{N+1}` + bump em `_SCHEMA_VERSION` + update nesta memória.
- Migrations devem ser **idempotentes** (checar existência antes de criar).

## Enums (validados em `src/mem0ry/db/store.py`)

- **`_VALID_SCOPES`**: `global` / `project` / `context` / `session`.
- **`_VALID_MEMORY_TYPES`**: `fact` / `decision` / `pattern` / `log` (usado pra decay).
- **`_VALID_SOURCES`**: `claude-code` / `opencode` / `codex` / `manual` / `import` / `hook`.
- **`_VALID_KINDS`** (observations): `session-start` / `user-prompt` / `post-tool-use` / `pre-compact` / `session-end` / `log` / `other`.

Adicionar valor a um enum: editar o `_VALID_*` correspondente em `db/store.py`; centrais — todos os callers importam daqui.

## Superação de fatos

- `memories.superseded_by` (FK para `memories.id`) marca o antigo.
- `get_context()` e `search_memory()` **excluem** superseded rows.
- `evolve_fact` (MCP tool) faz: set `superseded_by` + soft-delete do antigo + insert do novo.

## When editing…

- **Bump de schema**: criar `migrate_v8_to_v9` em `db/migrate.py`, atualizar `_SCHEMA_VERSION`, **atualizar esta memória**.
- **Novo enum value**: editar `db/store.py` (e nada mais — todos importam dali).
- **Nova tabela**: adicionar DDL em `db/schema.py`, migration em `db/migrate.py`, índice apropriado.
- **Tabela nova auditável**: garantir que `db/store_audit.py` registra mutações.
- Testar migration em DB v{N-1} com `mymem0ry migrate --reprocess` (em DB de teste, não no real).
