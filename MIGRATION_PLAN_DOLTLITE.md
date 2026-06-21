# Plano de Migração para DoltLite

## Contexto

O spike em `spike/doltlite-poc` demonstrou que DoltLite não é drop-in para o myMem0ry devido a incompatibilidades com FTS5 e triggers que dependem de `rowid`. Este documento descreve o plano para viabilizar a migração.

## Problemas Identificados

### 1. FTS5 Triggers usam `NEW.rowid`
**Problema**: O schema v8 cria triggers que referenciam `NEW.rowid` para sincronizar a tabela FTS5:
```sql
CREATE TRIGGER memories_fts_ai AFTER INSERT ON memories
BEGIN
    INSERT INTO memories_fts(rowid, title, content, tags)
    VALUES (NEW.rowid, ...);
END
```

**Impacto**: DoltLite não expõe `rowid` em tabelas com PRIMARY KEY TEXT.

### 2. Busca FTS5 usa `rowid`
**Problema**: As queries de busca FTS5 fazem join via `rowid`:
```sql
SELECT id, content FROM memories
WHERE rowid IN (SELECT rowid FROM memories_fts WHERE content MATCH '...')
```

**Impacto**: Queries de busca full-text não funcionam no DoltLite.

### 3. Python Binding exige shared extension
**Problema**: O binding Python do DoltLite só funciona com Python que tenha `_sqlite3` como shared extension (não funciona com python-build-standalone do `uv`).

**Impacto**: Instalação via `uv tool install` pode falhar.

## Plano de Implementação

### Fase 1: Refatorar Schema para Eliminar Dependência de `rowid`

#### 1.1 Adicionar coluna `fts_rowid` explícita
**Arquivo**: `src/mem0ry/db/schema.py`

Adicionar coluna `fts_rowid INTEGER` na tabela `memories` para substituir `rowid`:

```sql
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    fts_rowid INTEGER UNIQUE,  -- NOVO
    content TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    ...
)
```

**Migração**: Criar `migrate_v8_to_v9()` que:
1. Adiciona coluna `fts_rowid`.
2. Popula com valores sequenciais baseados em `rowid` atual.
3. Atualiza `memories_fts` para usar `fts_rowid`.

#### 1.2 Atualizar Triggers FTS5
**Arquivo**: `src/mem0ry/db/schema.py`

Substituir `NEW.rowid` por `NEW.fts_rowid`:

```sql
CREATE TRIGGER memories_fts_ai AFTER INSERT ON memories
WHEN NEW.deleted_at IS NULL AND (NEW.superseded_by IS NULL OR NEW.superseded_by = '')
BEGIN
    INSERT INTO memories_fts(rowid, title, content, tags)
    VALUES (NEW.fts_rowid, COALESCE(NEW.title, ''), NEW.content, NEW.tags);
END
```

#### 1.3 Atualizar Queries de Busca FTS5
**Arquivos**:
- `src/mem0ry/db/store_memories/search.py`
- `src/mem0ry/db/store_memories/context.py`

Substituir `WHERE rowid IN` por `WHERE fts_rowid IN`:

```sql
SELECT id, content FROM memories
WHERE fts_rowid IN (SELECT rowid FROM memories_fts WHERE content MATCH '...')
```

### Fase 2: Abstrair Camada de Conexão

#### 2.1 Criar factory de conexão
**Arquivo**: `src/mem0ry/db/connection.py`

Adicionar função `get_connection()` que detecta se DoltLite está disponível e usa o binding apropriado:

```python
def get_connection(db_path: Path) -> sqlite3.Connection:
    """Retorna conexão SQLite ou DoltLite baseado no ambiente."""
    if _should_use_doltlite():
        import doltlite  # type: ignore
        return sqlite3.connect(str(db_path))
    else:
        return sqlite3.connect(str(db_path))
```

#### 2.2 Detectar engine em runtime
**Arquivo**: `src/mem0ry/db/connection.py`

Adicionar função para detectar se o DB é DoltLite:

```python
def is_doltlite_db(conn: sqlite3.Connection) -> bool:
    """Detecta se o banco usa engine DoltLite."""
    try:
        result = conn.execute("SELECT doltlite_engine()").fetchone()
        return result and result[0] == "prolly"
    except sqlite3.OperationalError:
        return False
```

### Fase 3: Implementar Sync com DoltLite

#### 3.1 Adicionar comandos de version control
**Arquivo**: `src/mem0ry/cli/sync.py` (novo)

Criar comandos CLI:
- `mymem0ry sync init` — inicializa remote DoltLite
- `mymem0ry sync push` — commit + push
- `mymem0ry sync pull` — pull + merge
- `mymem0ry sync status` — mostra status de branch/commits

#### 3.2 Auto-commit após writes
**Arquivo**: `src/mem0ry/db/store_memories/crud.py`

Após operações de write, se DoltLite estiver ativo:
```python
if is_doltlite_db(conn):
    conn.execute("SELECT dolt_add('-A')")
    conn.execute("SELECT dolt_commit('-m', 'auto: memory write')")
```

#### 3.3 Configuração
**Arquivo**: `src/mem0ry/config.py`

Adicionar variáveis de ambiente:
```python
MEM0RY_SYNC_REMOTE: str | None  # file:// ou http://
MEM0RY_SYNC_BRANCH: str = "main"
MEM0RY_SYNC_AUTO_COMMIT: bool = True
```

### Fase 4: Resolver Compatibilidade Python

#### 4.1 Documentar requisitos
**Arquivo**: `README.md`, `AGENTS.md`

Adicionar seção sobre requisitos de Python para DoltLite:
- Python com `_sqlite3` como shared extension
- Exemplos: Homebrew Python, distro Python, pyenv, conda
- **Não funciona**: python-build-standalone (padrão do `uv python install`)

#### 4.2 Fallback para SQLite puro
**Arquivo**: `src/mem0ry/db/connection.py`

Se DoltLite não estiver disponível ou Python for incompatível, usar SQLite puro sem sync:
```python
try:
    import doltlite
    # usa DoltLite
except (ImportError, DoltliteLoadError):
    # fallback para SQLite puro
    pass
```

### Fase 5: Testes e Validação

#### 5.1 Testes de schema
**Arquivo**: `tests/test_schema_doltlite.py` (novo)

Testar:
- Criação de schema v9 com `fts_rowid`
- Triggers FTS5 funcionam no DoltLite
- Busca FTS5 via `fts_rowid` retorna resultados corretos

#### 5.2 Testes de sync
**Arquivo**: `tests/test_sync_doltlite.py` (novo)

Testar:
- `dolt_commit` após write
- `dolt_push`/`dolt_pull` com remote `file://`
- Merge de conflitos (mesma memória editada em duas máquinas)
- Resolução de conflitos via `dolt_conflicts_resolve`

#### 5.3 Testes de compatibilidade
**Arquivo**: `tests/test_connection.py` (novo)

Testar:
- Detecção automática de engine (DoltLite vs SQLite)
- Fallback para SQLite puro quando DoltLite não disponível
- Migração de schema v8 → v9

## Cronograma Estimado

| Fase | Tarefas | Esforço |
|------|---------|---------|
| Fase 1 | Refatorar schema e queries | 2-3 dias |
| Fase 2 | Abstrair camada de conexão | 1 dia |
| Fase 3 | Implementar sync CLI | 2-3 dias |
| Fase 4 | Documentação e fallback | 1 dia |
| Fase 5 | Testes e validação | 2-3 dias |
| **Total** | | **8-11 dias** |

## Riscos e Mitigações

### Risco 1: Performance degrada com `fts_rowid`
**Mitigação**: Benchmark antes/depois. Se degradação > 20%, considerar alternativa (ex: manter `rowid` virtual via view).

### Risco 2: Migração v8 → v9 quebra instalações existentes
**Mitigação**: Script de migração automático em `mymem0ry doctor`. Testar em DBs reais.

### Risco 3: Python incompatível causa falhas silenciosas
**Mitigação**: Detecção explícita em `mymem0ry doctor` com mensagem clara. Fallback para SQLite puro.

### Risco 4: DoltLite ainda é jovem (v0.11.15)
**Mitigação**: Manter SQLite puro como fallback. Documentar que DoltLite é experimental.

## Alternativas Consideradas

### Alternativa A: Manter SQLite + Git simples
**Prós**: Zero mudança de schema, compatibilidade total, instalação fácil.
**Contras**: Sem merge real (last-write-wins), perde histórico de mudanças.

### Alternativa B: Usar cr-sqlite
**Prós**: Extensão SQLite, merge via CRDT, sem mudança de engine.
**Contras**: Complexidade adicional (site_id, crsql_changes), insert 2.5x mais lento.

### Alternativa C: DoltLite (este plano)
**Prós**: Merge real via version control, histórico nativo, push/pull.
**Contras**: Esforço de migração significativo, dependência de Python compatível.

## Recomendação

Implementar este plano **apenas se** o merge real de dados for crítico para o caso de uso. Caso contrário, seguir com **Alternativa A** (SQLite + Git simples) como MVP.

## Referências

- Spike: branch `spike/doltlite-poc`
- DoltLite docs: https://github.com/dolthub/doltlite
- Schema v8: `src/mem0ry/db/schema.py`
- FTS5 queries: `src/mem0ry/db/store_memories/search.py`
