# Fase 3 — Plano de Implementação

> Estado actual: Fases 1 e 2 completas. 245 testes passando.
> Version: 0.2.0 → bump para 0.3.0 após Fase 3.

---

## Estado actual (o que já existe)

- **245 testes** passando, 0 falhanhos
- **ruff/mypy**: erros apenas em ficheiros de teste pré-existentes (11 imports unused)
- **CI**: nenhum
- **Docs**: README básico, sem CHANGELOG, sem CONTRIBUTING
- **Coverage**: `fail_under = 80` no pyproject.toml mas sem CI para validar
- **Packaging**: entry points definidos (`mymem0ry`, `mymem0ry-mcp`), mas não publicado no PyPI
- **Dependência fantasma**: `openai>=1.0` no pyproject.toml mas não é usada em lado nenhum

---

## 3.1 Observabilidade — PARCIALMENTE FEITO

### Já implementado
- `mymem0ry stats` — overview da base (total, por scope, por source, projects)
- `mymem0ry projects` — lista projectos com memórias
- Logging estruturado em `utils/logging.py`

### Falta

| Tarefa | Ficheiro | Detalhes |
|---|---|---|
| `mymem0ry doctor` | `src/mem0ry/cli/main.py` | Verifica: spaCy model instalado, sqlite-vec disponível, DB existe/schema ok, índices BM25/FTS5/vector presentes, permissoes de escrita |
| Substituir `print()` por `logging` | `search_bm25.py`, `benchmark.py` | Ainda usam `print()` para output de diagnóstico — trocar por `logger.info()` |
| Comando `stats` com formatação richer | `cli/main.py` | Atualmente é texto simples — considerar tabela formatada |

---

## 3.2 CI/CD e qualidade de código

### Tarefas

| Tarefa | Ficheiro | Detalhes |
|---|---|---|
| GitHub Actions workflow | `.github/workflows/ci.yml` | Trigger em push/PR para main. Steps: checkout, install uv, `uv sync`, `uv run ruff check .`, `uv run mypy src/mem0ry`, `uv run pytest --cov` |
| Badge de CI no README | `README.md` | `[![CI](https://github.com/cccadet/myMem0ry/actions/workflows/ci.yml/badge.svg)]` |
| Limpar imports unused nos testes | 6 ficheiros de teste | Ver lista abaixo |
| Remover dep `openai` fantasma | `pyproject.toml` | `openai>=1.0` não é importada em lado nenhum — remover |
| Coverage mínimo 70% no CI | `pyproject.toml` | Já está `fail_under = 80` — só precisa de rodar `--cov` no CI |
| Configurar mypy menos estrito | `pyproject.toml` ou `mypy.ini` | Adicionar `[[tool.mypy]]` com `ignore_missing_imports = true` para sqlite_vec, rank_bm25, spacy |

### Testes com imports unused a corrigir

```
tests/test_mcp_server.py:5      — os importado mas não usado
tests/test_mcp_server.py:25     — _session_id, _session_title importados mas não usados
tests/test_pipeline_dataset.py:7 — MagicMock, patch importados mas não usados
tests/test_search_bm25.py:72    — variável results assignada mas não usada
tests/test_search_fts.py:49     — variável results assignada mas não usada
tests/test_search_full.py:6     — MagicMock importado mas não usado
tests/test_search_full.py:10    — _extract_keywords importado mas não usado
tests/test_temporal_extra.py:47 — variável result assignada mas não usada
tests/test_utils.py:40          — nome de variável ambíguo `l`
```

### Template do ci.yml

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --group dev
      - run: uv run ruff check .
      - run: uv run mypy src/mem0ry
      - run: uv run pytest --cov --cov-report=term-missing
```

---

## 3.3 Documentação

### Tarefas

| Tarefa | Ficheiro | Conteúdo |
|---|---|---|
| CHANGELOG.md | `CHANGELOG.md` | Seções: Unreleased, 0.3.0 (Fase 2+3), 0.2.0 (Fase 1). Formato Keep a Changelog |
| CONTRIBUTING.md | `CONTRIBUTING.md` | Como correr testes, lint, como adicionar parsers/tools, convenções de código (link para AGENTS.md) |
| README renovado | `README.md` | Ver detalhes abaixo |

### README.md — estrutura sugerida

```
# myMem0ry — Memória pessoal para agentes de IA

> Zero API keys. Offline. Python puro.

## O que faz
- Ingests conversas do ChatGPT, Gemini, Claude → .md indexados
- Busca semântica (spaCy + sqlite-vec + BM25/FTS5/hybrid)
- MCP server com escopos (global/project/session)
- Funciona com Claude Code, OpenCode, Cursor

## Quick start
  $ uvx mymem0ry split data/openai/export
  $ uvx mymem0ry search "python decorators"
  $ uvx mymem0ry search "auth" --backend hybrid --expand

## Arquitectura
  [diagrama ASCII]
  Conversas → split → .md + embeddings → busca híbrida → MCP tools → agente

## Escopos de memória
  | scope | uso |
  | global | preferências, stack |
  | project | decisões técnicas, bugs |
  | session | resumo da sessão |

## MCP Tools
  [tabela das 9 tools]

## Hooks para agentes
  [instruções para CLAUDE.md e opencode.json]

## Comandos CLI
  [tabela completa]

## Configuração
  [variáveis de ambiente]

## Desenvolvimento
  $ uv sync --group dev
  $ uv run pytest
  $ uv run ruff check .
```

---

## 3.4 Packaging

### Tarefas

| Tarefa | Ficheiro | Detalhes |
|---|---|---|
| Adicionar metadata PyPI | `pyproject.toml` | `license`, `classifiers`, `urls` (Homepage, Issues, Changelog) |
| Remover dep `openai` | `pyproject.toml` | Não é usada — remover das dependencies |
| Trocar build backend | `pyproject.toml` | Considerar `hatchling` em vez de `uv_build` para compatibilidade com `pip install` |
| Bump version | `pyproject.toml` | `0.2.0` → `0.3.0` |
| Testar `uvx` local | — | `uv build && uv tool install ./dist/mymem0ry-0.3.0-py3-none-any.whl` |

### pyproject.toml — adições sugeridas

```toml
[project]
license = "MIT"
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Utilities",
]
keywords = ["memory", "mcp", "spacy", "semantic-search", "ai-agent"]

[project.urls]
Homepage = "https://github.com/cccadet/myMem0ry"
Issues = "https://github.com/cccadet/myMem0ry/issues"
Changelog = "https://github.com/cccadet/myMem0ry/blob/main/CHANGELOG.md"
```

---

## ROADMAP.md — atualizar

Depois de completar a Fase 3, atualizar o `ROADMAP.md`:
- Marcar todos os itens como `[x]` completados
- Adicionar secção "Próximos passos" com ideias pós-v1.0
- Atualizar a decisão de arquitectura: embeddings usa spaCy vectors (não all-MiniLM-L6-v2)

---

## Ordem recomendada de implementação

```
1. Limpar imports unused nos testes (5 min)
2. Remover dep openai do pyproject.toml (1 min)
3. Comando mymem0ry doctor (30 min)
4. GitHub Actions ci.yml (15 min)
5. mypy config: ignore_missing_imports (5 min)
6. CHANGELOG.md (15 min)
7. CONTRIBUTING.md (10 min)
8. README.md renovado (30 min)
9. pyproject.toml metadata + bump version (10 min)
10. Testar uvx local (10 min)
11. Substituir prints por logging (10 min)
12. Badge CI no README (2 min)
13. Atualizar ROADMAP.md (10 min)
```

Tempo estimado total: ~2.5h
