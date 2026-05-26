# Fase 4 — Novos Scopes de Memória (v0.4.0)

> Objetivo: reestruturar o sistema de escopos de memória para separação dimensional
> (onde a memória vive) em vez de tipo cognitivo (o que a memória é).

---

## Decisões de design

| Decisão | Escolha | Motivo |
|---|---|---|
| Scopes | `session \| context \| project \| global` | Resolução automática por cwd, qualquer ferramenta usa o mesmo |
| Project ID | git remote URL raw (ex: `github.com/cccadet/myMem0ry`) | Funciona para qualquer forja, legível. Fallback: `str(cwd)` se sem git |
| Context | Genérico — branch, worktree, feature, qualquer subdivisão | Flexível, não limitado a git |
| Memory type | `fact \| decision \| pattern \| log` (coluna interna) | Decaimento diferenciado + busca filtrada |
| Retrocompatibilidade | Não — reprocessa dados | Uso pessoal, sem terceiros |

---

## Novo schema

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    project_id TEXT,
    project_path TEXT,
    context TEXT,
    session_id TEXT,
    memory_type TEXT NOT NULL DEFAULT 'log',
    source TEXT NOT NULL DEFAULT 'manual',
    tags TEXT NOT NULL DEFAULT '[]',
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    file_path TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT
)
```

**Scopes:**

| Scope | Identificador | O que guarda | Exemplo |
|---|---|---|---|
| `session` | `session_id` (UUID) | Contexto imediato da sessão | "Tentando fixar o bug no auth flow" |
| `context` | `context` (branch/worktree) | Decisões de uma branch/worktree | "Na feat/auth, decidimos usar JWT" |
| `project` | `project_id` (git remote URL) | Decisões arquiteturais do projeto | "Este projeto usa FastAPI + SQLite" |
| `global` | — | Preferências do usuário | "Prefiro PT-BR nos commits" |

**Memory types (coluna `memory_type`):**

| Tipo | Duração | Uso |
|---|---|---|
| `fact` | Indefinida | Fatos, preferências, stack |
| `decision` | Indefinida | Decisões técnicas |
| `pattern` | Indefinida, decai se não re-observado | Padrões repetidos |
| `log` | 30-90 dias, decai | Registos de sessão, logs |

---

## Resolução automática de contexto

```
Agente chama get_context(cwd="/home/xixo/Projetos/myMem0ry")
  |
  +-- 1. resolve_project_id(cwd)
  |     +-- git remote get-url origin -> "github.com/cccadet/myMem0ry"
  |     |   (fallback: str(cwd) se nao for git repo)
  |
  +-- 2. resolve_context(cwd)
  |     +-- git rev-parse --abbrev-ref HEAD -> "main"
  |     |   (fallback: null se nao for git repo)
  |
  +-- 3. session_id -> do hook ou auto-gerado
  |
  +-- 4. SELECT com cascata:
         session (s1) U context (main) U project (github.com/.../myMem0ry) U global
         top_k distribuido pelos 4 niveis
```

---

## Ficheiros a alterar

### Novos ficheiros

| Ficheiro | Descricao |
|---|---|
| `src/mem0ry/utils/git_context.py` | `resolve_project_id()`, `resolve_context()`, `resolve_full_context()` |
| `tests/test_git_context.py` | Testes com mock de subprocess |

### Ficheiros modificados

| Ficheiro | Mudancas |
|---|---|
| `src/mem0ry/db/schema.py` | Schema v3, novos scopes, memory_type, access_count, last_accessed_at |
| `src/mem0ry/db/store.py` | Novo CRUD com project_id, context, memory_type; cascata 4 niveis; touch_memory, decay_memories |
| `src/mem0ry/db/migrate.py` | `migrate_v2_to_v3()` — drop + reingest |
| `src/mem0ry/mcp_server.py` | Tools recebem `cwd` e resolvem contexto automaticamente |
| `src/mem0ry/cli/main.py` | `migrate --reprocess`, `decay`, `stats` com by_type/by_context |
| `src/mem0ry/config.py` | Sem mudancas significativas |
| `AGENTS.md` | Atualizar scopes e key facts |
| `pyproject.toml` | Bump 0.4.0 |
| `tests/test_db_schema.py` | Novas colunas, v3 |
| `tests/test_db_store.py` | Novos params, cascata, touch, decay |
| `tests/test_db_migrate.py` | migrate_v2_to_v3 |
| `tests/test_mcp_server.py` | cwd param |

---

## Ordem de implementacao

```
 1. utils/git_context.py              (novo, isolado)
 2. tests/test_git_context.py         (novo, valida #1)
 3. db/schema.py                      (breaking: novo schema v3)
 4. db/store.py                       (breaking: novo CRUD)
 5. tests/test_db_schema.py           (atualiza)
 6. tests/test_db_store.py            (atualiza)
 7. db/migrate.py                     (novo migrate_v2_to_v3)
 8. tests/test_db_migrate.py          (atualiza)
 9. mcp_server.py                     (breaking: novas assinaturas)
10. tests/test_mcp_server.py          (atualiza)
11. cli/main.py                       (comandos novos)
12. AGENTS.md                         (documentacao)
13. pyproject.toml                    (bump 0.4.0)
14. ruff + mypy + pytest              (validacao final)
```
