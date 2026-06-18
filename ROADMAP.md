# myMem0ry — Roadmap

> Sistema de memória pessoal para agentes de IA. Offline, zero API keys, Python puro.
> Filosofia: **o agente faz os resumos, tu fazes as buscas.**

---

## O que está feito (schema v8)

- [x] Embeddings locais (spaCy word vectors 300-dim, sqlite-vec)
- [x] Busca híbrida com RRF fusion (BM25 + vector + FTS5 + ripgrep)
- [x] Query expansion semântica com spaCy
- [x] Parsers: OpenAI (ChatGPT JSON), Gemini (Google Takeout), Claude (.jsonl + export JSON)
- [x] Schema v8: 4 scopes, 4 memory types, observations, handoffs, audit_log
- [x] Resolução automática de contexto via git (remote URL + branch)
- [x] MCP server com 12 tools + health endpoint + hook receiver
- [x] CLI completo: split, search, index, migrate, stats, projects, doctor, benchmark, decay, expand, dataset, backup, restore, handoff, observe, hooks
- [x] Hooks para Claude Code, OpenCode, Cursor, Codex, Gemini CLI
- [x] CI (GitHub Actions: ruff + mypy + pytest --cov, coverage gate 80%)
- [x] Decay + retenção por tiers (log/pattern/fact/decision) com salience + access_count
- [x] Handoffs tipados entre agentes (tabela + tools + session-start auto-fetch)
- [x] Lifecycle hooks HTTP (POST /hook) com sanitização + spool + 7 kinds
- [x] Streamable-HTTP transport + bearer auth + host allowlist + CORS
- [x] Web UI read-only com dark mode (25 rotas, FTS5 search, renderização markdown)
- [x] Backup/restore (tarball com DB + conversations)
- [x] Audit log de mutations
- [x] Evolve_fact com supersession chain
- [x] CHANGELOG.md, CONTRIBUTING.md, README, AGENTS.md
- [x] Publicável no PyPI (hatchling, entry points, classifiers)

---

## Decisões de arquitectura

| Decisão | Escolha | Motivo |
|---|---|---|
| Embeddings | spaCy word vectors (300-dim, offline) | Zero custo, sem API key, sem modelo extra |
| Vector store | sqlite-vec | Sem deps externas, embutido no SQLite |
| Resumos | Feitos pelo agente activo | Zero custo, contexto completo, melhor que templates |
| Refactor de memories | `evolve_fact` (chamado pelo agente) | Explícito, auditável, sem heurística cega |
| Schema | SQLite v8 (scopes + memory_type + access tracking + observations + handoffs + audit_log) | Simples, portátil, evolutivo |
| MCP | FastMCP Python SDK (stdio + SSE + streamable-http) | Multi-transport, mesma SDK |
| Linguagem | Python puro | Consistência, sem runtime extra |
| Hooks | HTTP POST + spool dir + sanitização | Fire-and-forget, não bloqueia agente |
| Multi-machine | `backup`/`restore` + rsync do `data/` | Suficiente para homelab, sem servidor central |

---

## Não está no scope

Tudo o que envolva LLM adicional, sincronização automática entre máquinas, ou
camadas de consolidação sobre o que o agente já faz:

- ~~Consolidação LLM-driven~~ — o modelo activo já resume melhor
- ~~Consolidação rule-based automática~~ — gera resumos medíocres sem contexto
- ~~Lint automático de contradições~~ — `evolve_fact` é o caminho explícito
- ~~Thin-client CLI / servidor remoto multi-host~~ — backup/restore cobre o caso
- ~~Wiki markdown versionada~~ — `evolve_fact` + `superseded_by` na BD é suficiente
- ~~Multi-utilizador / equipa~~ — uso pessoal
- Fine-tuning de modelos (PLAN_FINETUNE.md → archived)
- Q&A pipeline temporal (temporal-qa-pipeline.md → archived)
- Suporte a outros formatos (Notion, Obsidian)

---

## Avaliação técnica atual (v0.25.4)

Resumo da avaliação abrangente realizada em 2026-06-16.

### Pontos fortes

- Arquitetura clara e modular com separação de responsabilidades; grandes módulos foram refatorados em pacotes menores.
- Feature-set maduro: memória escopada, handoffs, semantic search, hooks, web UI, backup/restore, auditoria, retenção e evolução de fatos.
- Documentação rica (README, AGENTS.md, CHANGELOG, CONTRIBUTING, docs/, .serena/memories/).
- CI bem estruturado e publicação PyPI automatizada.
- `ruff`, `mypy` e `bandit` passam sem erros; **602 testes passam**, cobertura total **83,53%**.
- Boa cobertura nas partes críticas (`db/store_memories/` 90%+, `conversations/search_bm25.py` 98%, `hooks/router.py` 88%, `cli/conversation.py` 98%).

### Pontos fracos / dívidas técnicas

- [x] Teste `test_config.py::test_defaults` falha localmente quando `.env` define `SPACY_MODEL=pt_core_news_lg`.
- [x] `mypy` reporta 2 erros de tipo (`pipeline/dataset.py`, `conversations/spacy_expand.py`).
- [x] Cobertura total 65%, abaixo do gate `fail_under=80`. **Agora 83,53% com 602 testes passando.**
- [x] Arquivos grandes violam o próprio estilo (500 linhas): `web/pages.py` (1355), `db/store_memories.py` (1051), `mcp_server.py` (939). **Ambos refatorados para pacotes menores.**
- [x] Funções com complexidade cognitiva alta: `get_context` (22), `export_memories_page` (16), `search_memories` (15), `forget_sweep` (14). **`get_context` e `search_memories` simplificados; `forget_sweep` e `export_memories_page` movidos para pacotes menores.**
- [x] Bandit aponta muitos `except Exception: pass`, subprocessos com caminho parcial, uso de `pickle`, `urlopen` sem validação de scheme e SQL dinâmico. **Todos os alertas auditados e resolvidos; `bandit -r src/mem0ry` reporta 0 issues.**
- [x] Inconsistência entre `MEM0RY_HOST`/`MEM0RY_PORT` (config.py/documentação) e `MCP_HOST`/`MCP_PORT` (mcp_server.py, cli/server.py, daemon.py, Dockerfile). **`MemoryConfig.server_host/server_port` unifica com fallback para `MCP_HOST`/`MCP_PORT`.**
- [x] Módulos sem cobertura: `daemon.py`, `utils/update_check.py`, partes da CLI. **Cobertos por `test_daemon.py`, `test_update_check.py`, `test_cli_*` e novos testes de `mcp_server`.**

---

## Checklist de melhorias

### Qualidade de build

- [x] Corrigir `tests/test_config.py` para isolar `SPACY_MODEL`
- [x] Resolver 2 erros de tipo do `mypy`
- [x] Subir cobertura para ≥80% (atingido **83.53%** — **602 testes** passando)

### Arquitetura / modularização

- [x] Quebrar `web/pages.py` em módulos menores (`src/mem0ry/web/pages/` com 9 módulos, todos ≤400 linhas)
- [x] Quebrar `db/store_memories.py` em módulos menores (`src/mem0ry/db/store_memories/` com 8 módulos)
- [x] Reduzir complexidade cognitiva de `get_context` e `search_memories` (extração de helpers para `context.py` e `search.py`)

### Segurança e robustez

- [x] Auditar `except Exception: pass` e logar falhas (todos substituídos por `logger.warning`)
- [x] Validar/justificar uso de `pickle` no cache BM25 (`# nosec B301/B403`, cache local gerado pelo próprio processo)
- [x] Adicionar testes com mocks para subprocessos e requisições HTTP
- [x] Revisar SQL dinâmico e garantir whitelists explícitas (placeholders em todas as queries dinâmicas; `# nosec B608` documentado)

### Configuração / ops

- [x] Padronizar `MEM0RY_HOST`/`MEM0RY_PORT` vs `MCP_HOST`/`MCP_PORT`
- [x] Corrigir Dockerfile para usar variáveis consistentes

### Bugs corrigidos durante a rodada

- [x] `tests/test_config.py::test_defaults` falhava com `.env` local `pt_core_news_lg`.
- [x] `src/mem0ry/cli/hooks.py:_hooks_dir()` retornava o módulo Python `src/mem0ry/hooks/` em vez do diretório real de hooks `hooks/` em desenvolvimento.
- [x] Ordem das rotas web `/project/{project_id:path}` e `/project/{project_id:path}/observations` — a rota greedy passou a vir depois, evitando que `/observations` fosse capturada como `project_id`.

### Novos testes adicionados

- [x] `tests/test_daemon.py` — 22 testes cobrindo PID, health, spawn, stop, status, edge cases Windows.
- [x] `tests/test_update_check.py` — 11 testes para cache e fetch PyPI.
- [x] `tests/test_cli_diagnostics.py` — 13 testes para version, stats, projects, doctor, spacy checks.
- [x] `tests/test_cli_hooks.py` — 7 testes para path/config/usage/detect.
- [x] `tests/test_cli_server.py` — 5 testes para serve detach/foreground e observe.
- [x] `tests/test_auth_extra.py` — 14 testes para bearer/host/CORS middleware.
- [x] `tests/test_web.py` — 43 testes de UI web (dashboard, search, edit, import, export, handoffs, observations, trash).
- [x] `tests/test_mcp_tools.py` — 17 testes das tools MCP.
- [x] `tests/test_cli_conversation.py` — 12 testes dos comandos `split`, `search`, `benchmark`, `expand`, `index`.
- [x] `tests/test_mcp_server_extra.py` — 24 testes de ferramentas e endpoints HTTP do MCP server.

---

## Referências

- [akitaonrails/ai-memory](https://github.com/akitaonrails/ai-memory) — comparação inicial (Rust, v0.3.2)
- [agentmemory](https://github.com/rohitg00/agentmemory) — referência de arquitectura
- [basic-memory](https://github.com/basicmachines-co/basic-memory) — markdown source of truth (avaliado, rejeitado)
- [sqlite-vec](https://github.com/asg017/sqlite-vec) — extensão vetorial para SQLite
- [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — compile-not-retrieve pattern
