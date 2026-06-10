# Retenção e evolução

Implementado em `src/mem0ry/db/retention.py`. Três tiers derivados de `memory_type`.

## Tiers

| `memory_type` | Classe | Retenção | Decay |
|---|---|---|---|
| `log` | working | 90d máx | por saliência |
| `pattern` | procedural | 365d máx | por frequência |
| `fact` / `decision` | semantic | **indefinida** | auto-pinned |

## Saliência

- `db/retention.py` calcula saliência (idade × acesso × importância inferida).
- `memory_forget_sweep` (MCP tool): dry-run por default; `execute=True` aplica.
- **Soft-delete** de baixa saliência; **hard-delete** após grace.

## Pin/unpin

- `memory_pin` / `memory_unpin` (MCP tools) isentam/reativam decay.
- `fact` e `decision` são auto-pinned na criação (semântica indefinida).

## Evolução de fatos

- `evolve_fact` (MCP tool, `mcp_server.py:530`): agente LLM consolida fatos contraditórios.
- Fluxo: set `superseded_by` + soft-delete do antigo + insert do novo.
- `get_context()` e `search_memory()` **excluem** rows superseded — evolução é invisível para leitura.
- Sem heurística automática — decisão é do agente (instruction-based).

## Audit log

- `db/store_audit.py` grava toda mutação: create, delete, import, handoff, evolve.
- Inspecionável em `/audit` (web UI) e via SQL.
- **Não bypassar** em código novo — mutação sem audit = bug difícil de diagnosticar.

## Comandos CLI

- `mymem0ry decay [--days 90] [--dry-run]` — remove session logs antigos.
- `mymem0ry memory forget-sweep` (via MCP ou equivalente) — tiers de retenção.

## When editing…

- **Mudar tier de retenção**: `db/retention.py`. Verificar que `fact`/`decision` continuam auto-pinned.
- **Mudar cálculo de saliência**: manter pure function (testável); atualizar testes em `tests/test_retention.py` (se existir).
- **Bug "memória sumiu"**: checar `superseded_by` na tabela `memories`; superseded = invisível por design.
- **Adicionar mutação nova**: gravar em `audit_log` — caso contrário a UI `/audit` fica incompleta.
- **Evoluir fato programaticamente** (não via LLM): usar `evolve_fact` MCP tool, não SQL direto.
