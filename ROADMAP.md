# myMem0ry — Roadmap

> Ferramenta de memória pessoal, local, sem API key externa, para agentes de IA.  
> Filosofia: **o agente faz os resumos, tu fazes as buscas.**

---

## Visão geral

```
Conversas históricas (ChatGPT, Gemini, Claude)
        ↓
    [split + ingest]
        ↓
  Base de memórias indexadas
  (scope: global / project / session)
        ↓
    [MCP Server]
        ↓
  Agentes (Claude Code, OpenCode, Cursor...)
```

---

## Fase 1 — Fundação semântica ✅

### 1.1 Embeddings locais

- [x] Adicionar `sqlite-vec` como backend vetorial (zero deps externas, embutido no SQLite)
- [x] Gerar embedding por chunk de conversa no momento do `split`
- [x] Armazenar embeddings associados ao ficheiro `.md` correspondente
- [x] Embeddings usa spaCy word vectors (300-dim, `pt_core_news_lg`) — não all-MiniLM-L6-v2

### 1.2 Busca híbrida

- [x] Implementar RRF fusion (Reciprocal Rank Fusion) combinando BM25 + vector
- [x] Novo flag `--backend hybrid` no comando `search`
- [x] Benchmark interno: comparar recall do hybrid vs BM25-only vs FTS5

### 1.3 Suporte a Claude exports

- [x] Parser para `.jsonl` do Claude Code (`~/.claude/projects/`)
- [x] Parser para JSON de export do claude.ai
- [x] Auto-detecção no comando `split` (junto com OpenAI e Gemini)

---

## Fase 2 — Escopos de memória + captura ativa ✅

### 2.1 Novo schema de memória

- [x] Migrar para novo schema com scope, project_path, session_id, source, tags
- [x] Índice SQLite por `scope` + `project_path` para queries eficientes
- [x] Comando `mymem0ry migrate` para converter memórias existentes

### 2.2 Novas ferramentas MCP

- [x] Implementar `save_memory` com validação de scope
- [x] Implementar `get_context` com agregação dos 3 escopos
- [x] Implementar `list_scopes` e `memory_stats`
- [x] Implementar `end_session`
- [x] Actualizar `search_memory` existente para suportar filtro por scope

### 2.3 Captura ativa via hooks

- [x] Documentar instrução de hook para Claude Code (`CLAUDE.md`)
- [x] Documentar instrução de hook para OpenCode (`opencode.json` system prompt)
- [x] Auto-geração de `session_id` baseado em timestamp + project_path

### 2.4 Auto-detecção de projecto

- [x] `get_context` e `save_memory` aceitam `project_path` e fazem match por prefixo
- [x] Fallback: se `project_path` não bate em nenhum projecto conhecido, usa scope global
- [x] Comando `mymem0ry projects` → lista projectos com memórias indexadas

---

## Fase 3 — Qualidade & visibilidade ✅

### 3.1 Observabilidade

- [x] Comando `mymem0ry stats` — total de memórias, por scope, por projecto, por fonte
- [x] Comando `mymem0ry projects` — lista directórios com memórias e contagens
- [x] Logging estruturado (substituir prints por `logging` com níveis)
- [x] Comando `mymem0ry doctor` — verifica dependências, índices, schema, permissões

### 3.2 CI/CD e qualidade de código

- [x] GitHub Actions: `pytest` + `mypy` + `ruff` em cada PR
- [x] Badge de CI no README
- [x] Cobertura mínima de testes: 80%
- [x] `mypy` config com `ignore_missing_imports` para deps não tipadas
- [x] Limpar imports unused nos testes
- [x] Remover dependência fantasma `openai>=1.0`

### 3.3 Documentação

- [x] CHANGELOG.md com versioning semântico
- [x] CONTRIBUTING.md
- [x] README renovado com arquitectura, quick start, escopos, MCP tools, CLI commands

### 3.4 Packaging

- [x] Metadata PyPI (license, classifiers, URLs)
- [x] Entry points limpos: `mymem0ry` e `mymem0ry-mcp`
- [x] Versão bumpada para 0.3.0

---

## Decisões de arquitectura

| Decisão | Escolha | Motivo |
|---|---|---|
| Embeddings | spaCy word vectors (300-dim, `pt_core_news_lg`) | Zero custo, offline, sem API key, sem modelo extra |
| Vector store | `sqlite-vec` | Sem deps externas, embutido no SQLite já existente |
| Resumos de sessão | Feitos pelo agente activo | Zero custo, o modelo já tem contexto completo |
| Schema de memórias | SQLite + JSON | Simples, portátil, sem servidor |
| MCP | `mcp` Python SDK | Já existente no projecto |
| Linguagem | Python puro | Consistência, sem Node.js runtime |

---

## Próximos passos (pós-v1.0)

1. **MCP via stdio** — suporte ao transporte stdio no MCP server (além do SSE actual), para compatibilidade com mais clientes
- Publicar no PyPI como `mymem0ry` (testar `uvx mymem0ry`)
- Dashboard web / viewer para memorias
- Sync entre máquinas
- Suporte a outros formatos (Notion, Obsidian, etc.)
- Benchmark automatizado vs grep puro
- Embeddings alternativos (sentence-transformers como opcional)
- API REST separada do MCP
- Memória de equipa / multi-utilizador

---

## Não está no scope (por enquanto)

- Dashboard web / viewer
- Sync entre máquinas
- Memória de equipa / multi-utilizador
- API REST separada do MCP
- Suporte a outros formatos (Notion, Obsidian, etc.)

---

## Referências

- [myMem0ry](https://github.com/cccadet/myMem0ry) — repositório principal
- [agentmemory](https://github.com/rohitg00/agentmemory) — referência de arquitectura (Node.js, mais complexo)
- [sqlite-vec](https://github.com/asg017/sqlite-vec) — extensão vetorial para SQLite
- [LongMemEval](https://github.com/xiaowu0162/LongMemEval) — benchmark de avaliação de memória
