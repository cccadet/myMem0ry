# myMem0ry — Roadmap

> Sistema de memória pessoal para agentes de IA. Offline, zero API keys, Python puro.
> Filosofia: **o agente faz os resumos, tu fazes as buscas.**

---

## O que está feito (v0.4.8)

- [x] Embeddings locais (spaCy word vectors 300-dim, sqlite-vec)
- [x] Busca híbrida com RRF fusion (BM25 + vector + FTS5 + ripgrep)
- [x] Query expansion semântica com spaCy
- [x] Parsers: OpenAI (ChatGPT JSON), Gemini (Google Takeout), Claude (.jsonl + export JSON)
- [x] Schema v3: 4 scopes (global/project/context/session), 4 memory types (fact/decision/pattern/log)
- [x] Resolução automática de contexto via git (remote URL, branch)
- [x] MCP server com 9 tools + 2 prompts + health endpoint
- [x] CLI completo: split, search, index, migrate, stats, projects, doctor, benchmark, decay, expand, dataset
- [x] Hooks para Claude Code, OpenCode, Cursor, Codex, Gemini CLI
- [x] CI (GitHub Actions: ruff + mypy + pytest --cov, coverage gate 80%)
- [x] Decay de sessões antigas (`decay_memories`)
- [x] CHANGELOG.md, CONTRIBUTING.md, README, AGENTS.md
- [x] Publicável no PyPI (hatchling, entry points, classifiers)

---

## Comparação com ai-memory (akitaonrails)

Análise feita contra `akitaonrails/ai-memory` v0.3.2 (Rust, 233 commits, 294 stars).

### Onde myMem0ry já compete ou supera

| Aspecto | myMem0ry | ai-memory |
|---|---|---|
| Embeddings offline | spaCy 300-dim, zero config | Requer OpenAI/Voyage/Google API key |
| Setup | `uv sync` + `mymem0ry doctor` | Docker ou Rust build + LLM config |
| Dependências | Python puro, sem API externa | Rust toolchain + LLM provider |
| Custo | Zero | Pago se usar LLM consolidation |
| Parsers de conversas | OpenAI + Gemini + Claude | Não importa conversas históricas |

### Gaps críticos para um MCP profissional

#### 1. Handoffs entre agentes (prioridade alta)

O ai-memory resolve o problema principal: parar um agente e continuar noutro.
myMem0ry tem `get_context` mas não tem handoffs tipados.

- [ ] **Tabela `handoffs`** — registro de handoff com status (open/accepted/expired), cwd, agent_kind, summary, open_questions, next_steps
- [ ] **Tool `memory_handoff_begin`** — criar handoff no fim da sessão
- [ ] **Tool `memory_handoff_accept`** — buscar e ack do handoff pendente no início da próxima sessão
- [ ] **Hook SessionStart** — auto-fetch handoff pendente via cwd matching
- [ ] **Hook SessionEnd** — auto-create handoff com resumo da sessão

#### 2. Lifecycle hooks robustos (prioridade alta)

Os hooks atuais são scripts shell básicos. O ai-memory tem:
- Fire-and-forget com timeout < 200ms
- Backpressure (HTTP 429 quando saturado)
- Sanitização de payload do agente
- Vocabulário de eventos: session-start, user-prompt, pre-tool-use, post-tool-use, pre-compact, session-end

- [ ] **Hook router HTTP** — endpoint `POST /hook` no MCP server para receber eventos de lifecycle
- [ ] **Payload sanitization** — strip de PII, validação de schema
- [ ] **Fire-and-forget com timeout** — hooks nunca bloqueiam o agente
- [ ] **Eventos expandidos** — capturar user-prompt, post-tool-use, pre-compact (não só session-start/end)
- [ ] **Tabela `observations`** — log imutável de todos os eventos capturados

#### 3. Wiki markdown como source of truth (prioridade média)

O ai-memory usa markdown git-versioned como fonte de verdade. myMem0ry gera .md
mas não mantém wiki consolidada.

- [ ] **Conceito de "pages"** — memórias consolidadas em páginas wiki (não só logs)
- [ ] **Git-versioning do diretório de memórias** — auto-commit em session-end
- [ ] **Consolidação** — no fim da sessão, reescrever logs em páginas coerentes
- [ ] **Wikilinks** — cross-references entre memórias relacionadas
- [ ] **Supersession chain** — histórico de versões de cada página

#### 4. Consolidação LLM-driven (prioridade média, opt-in)

O ai-memory oferece consolidação zero-LLM (rule-based) e LLM (rewrite).
myMem0ry não tem nenhum dos dois.

- [ ] **Consolidação rule-based** — sem LLM, sumário estruturado da sessão
- [ ] **Consolidação LLM (opt-in)** — com provider configurável (OpenAI, Anthropic, local)
- [ ] **Tool `memory_consolidate`** — trigger manual ou automático
- [ ] **Lint de contradições** — detectar decisões conflitantes entre memórias

#### 5. Memória com retenção inteligente (prioridade média)

O ai-memory tem 4 tiers com decay parametrizável. myMem0ry tem decay básico.

- [ ] **Tiers de retenção** — working (sessão), episodic (30d→180d), semantic (indefinido), procedural (frequency-decay)
- [ ] **Fórmula de salience** — `salience · exp(−λΔt) + σ · log(1+access_count) · exp(−μ · days_since_access)`
- [ ] **Soft-delete + hard-delete** — com período de grace
- [ ] **Pinned memories** — isentas de decay
- [ ] **Tool `memory_forget_sweep`** — preview (dry_run) + execução

#### 6. MCP transport e autenticação (prioridade média)

O ai-memory tem auth e transport robusto. myMem0ry tem HTTP básico.

- [x] **Streamable HTTP transport** — além de stdio e SSE, suportar streamable-http para clients remotos
- [x] **Bearer token auth** — proteger endpoints MCP/HTTP (MEM0RY_TOKEN env var)
- [x] **Host allowlisting** — DNS rebinding protection (MEM0RY_ALLOWED_HOSTS)
- [x] **CORS** — para web UI futura (MEM0RY_CORS_ORIGINS)

#### 7. Observabilidade e ops (prioridade baixa)

- [x] **Tool `memory_status`** — health check (counts, paths, version, uptime)
- [x] **Tool `memory_briefing`** — snapshot estruturado (stats + rules + recent + slots)
- [x] **Tool `memory_explore`** — digest em prosa do estado do projeto
- [x] **Audit log** — tabela de mutations para forensics
- [x] **Backup/restore** — `mymem0ry backup --to <tarball>` + `mymem0ry restore`

#### 8. Web UI (prioridade baixa)

- [x] **Read-only web viewer** — lista de projetos, árvore de pastas, FTS5 search, renderização markdown
- [x] **Dark mode** — montado no mesmo servidor MCP
- [x] **Auth integrada** — HTTP Basic com bearer token

#### 9. Multi-agente / multi-machine (futuro)

- [ ] **Workspace isolation** — projeto = workspace + project_id + path
- [ ] **Remote server mode** — bind 0.0.0.0 com auth para uso em LAN/homelab
- [ ] **Thin-client CLI** — `mymem0ry status`, `mymem0ry bootstrap` como HTTP clients do server

---

## Decisões de arquitectura

| Decisão | Escolha | Motivo |
|---|---|---|
| Embeddings | spaCy word vectors (300-dim, offline) | Zero custo, sem API key, sem modelo extra |
| Vector store | sqlite-vec | Sem deps externas, embutido no SQLite |
| Resumos | Feitos pelo agente activo (consolidação rule-based futura) | Zero custo |
| Schema | SQLite v3 (scopes + memory_type + access tracking) | Simples, portátil |
| MCP | FastMCP Python SDK | Já existente, stdio + SSE + streamable-http |
| Linguagem | Python puro | Consistência, sem runtime extra |
| Hooks | Shell scripts + HTTP endpoint (futuro) | Fire-and-forget, não bloqueia agente |

---

## Ordem sugerida de implementação

```
Prioridade alta (MCP profissional mínimo):
 1. Handoffs (tabela + tools + hook integration)        ~1 dia
 2. Hook router HTTP + payload sanitization              ~1 dia
 3. Observações imutáveis (tabela observations)          ~0.5 dia

Prioridade média (feature parity):
 4. Pages wiki + git-versioning                          ~1 dia
 5. Consolidação rule-based                              ~0.5 dia
 6. Retenção inteligente (tiers + salience + sweep)      ~1 dia
 7. Bearer auth + streamable-http robusto                ~0.5 dia

Prioridade baixa (diferenciação):
 8. Consolidação LLM-driven (opt-in)                     ~1 dia
 9. Web UI read-only                                     ~2 dias
10. Multi-machine (remote server + thin-client)          ~1 dia
```

---

## Não está no scope

- Fine-tuning de modelos (PLAN_FINETUNE.md → arquived)
- Q&A pipeline temporal (temporal-qa-pipeline.md → archived)
- Sync entre máquinas (futuro)
- Memória de equipa / multi-utilizador (futuro)
- Suporte a outros formatos (Notion, Obsidian) (futuro)

---

## Referências

- [akitaonrails/ai-memory](https://github.com/akitaonrails/ai-memory) — referência principal de comparação (Rust, v0.3.2)
- [agentmemory](https://github.com/rohitg00/agentmemory) — referência de arquitectura
- [basic-memory](https://github.com/basicmachines-co/basic-memory) — markdown source of truth
- [sqlite-vec](https://github.com/asg017/sqlite-vec) — extensão vetorial para SQLite
- [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — compile-not-retrieve pattern
