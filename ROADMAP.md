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

## Referências

- [akitaonrails/ai-memory](https://github.com/akitaonrails/ai-memory) — comparação inicial (Rust, v0.3.2)
- [agentmemory](https://github.com/rohitg00/agentmemory) — referência de arquitectura
- [basic-memory](https://github.com/basicmachines-co/basic-memory) — markdown source of truth (avaliado, rejeitado)
- [sqlite-vec](https://github.com/asg017/sqlite-vec) — extensão vetorial para SQLite
- [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — compile-not-retrieve pattern
