# AGENTS.md — myMem0ry

Sistema de memória pessoal com busca semântica, escopos (global/project/session) e MCP server.

## Stack

- Python 3.11+, uv, Typer CLI
- spaCy (word vectors pt_core_news_lg para query expansion + embeddings)
- sqlite-vec (vector store), rank-bm25, SQLite FTS5 (busca híbrida)
- MCP (FastMCP) para servidor de memória com escopos

## Estrutura

```
src/mem0ry/
├── __init__.py               # Exporta CLI app
├── config.py                 # MemoryConfig dataclass
├── mcp_server.py             # MCP server — 8 tools + 2 prompts (scoped)
├── cli/main.py               # Typer CLI
├── db/
│   ├── __init__.py
│   ├── connection.py          # get_connection() — SQLite + sqlite-vec
│   ├── schema.py              # init_schema() — tabela memories + índices
│   ├── migrate.py             # migrate_v1_to_v2() — .md → SQLite
│   └── store.py               # CRUD: create_memory, get_context, list_scopes, stats, end_session
├── parsers/
│   ├── base.py                # ParsedConversation, ParsedMessage, BaseParser ABC
│   ├── openai.py              # OpenAIParser — ChatGPT JSON exports (mapping tree)
│   ├── gemini.py              # GeminiParser — Google Takeout JSON (safeHtmlItem)
│   └── claude.py              # ClaudeCodeParser (JSONL) + ClaudeExportParser (JSON)
├── conversations/
│   ├── writer.py              # split_conversations() — export → .md por data
│   ├── search.py              # search() — ripgrep backend
│   ├── search_bm25.py         # search_bm25() — BM25Okapi
│   ├── search_fts.py          # search_fts() — SQLite FTS5
│   ├── search_hybrid.py       # search_hybrid() — RRF fusion BM25 + vector
│   ├── embeddings.py          # SpacyEncoder — spaCy doc vectors (300-dim)
│   ├── vector_store.py        # VectorStore — sqlite-vec wrapper
│   ├── spacy_expand.py        # SpacyConceptSearch + expand_query_spacy
│   └── benchmark.py           # run_benchmark() — compara backends
├── dataset/                   # Pipeline legado de fine-tuning ChatML
│   ├── builder.py
│   ├── temporal.py
│   ├── filter.py
│   ├── dedupe.py
│   ├── splitter.py
│   └── stats.py
├── pipeline/
│   └── dataset.py             # build_dataset_from_openai() — JSONL pipeline
└── utils/
    ├── filenames.py           # sanitize_title()
    ├── logging.py             # configure_logging()
    └── paths.py               # ensure_dir()
```

## Comandos CLI

```bash
mymem0ry split                        # Export (OpenAI/Gemini/Claude) → .md por data
mymem0ry search "qdrant"              # Busca (ripgrep default)
mymem0ry search "qdrant" --backend hybrid  # Busca híbrida BM25+vector
mymem0ry search "qdrant" --expand     # Busca com expansão spaCy
mymem0ry benchmark "python"           # Compara backends
mymem0ry expand "france"              # Tokens semanticamente relacionados
mymem0ry index                        # Constrói índices BM25 + FTS5 + vector
mymem0ry migrate                      # Migra .md existentes → SQLite memories
mymem0ry stats                        # Overview da base de memórias
mymem0ry projects                     # Lista projectos com memórias
mymem0ry dataset                      # Build ChatML JSONL (legacy)
```

## Escopos de memória

| Scope | O que guarda | save_memory args |
|---|---|---|
| `global` | Preferências, stack, padrões | `scope="global"` |
| `project` | Decisões técnicas, bugs, contexto | `scope="project", project_path="/abs/path"` |
| `session` | Resumo da sessão actual | `scope="session", session_id="abc123"` |

`get_context()` agrega os 3 níveis — sessão > projecto > global.

## MCP Tools

| Tool | Descrição |
|---|---|
| `log_message` | Log de mensagem na sessão actual |
| `save_memory` | Guardar memória com scope |
| `save_conversation` | Guardar conversa completa |
| `get_context` | Agregar contexto dos 3 escopos |
| `list_scopes` | Listar scopes com contagem |
| `end_session` | Marcar sessão como concluída |
| `search_memory` | Busca com expansão semântica |
| `read_memory` | Ler conteúdo de um ficheiro |
| `memory_stats` | Estatísticas da base |

## Testes & Lint

```bash
uv run pytest
uv run ruff check .
uv run mypy src/mem0ry
```

## Configuração

| Variável | Default | Uso |
|---|---|---|
| `EXPAND_TOP_K` | `10` | Tokens similares na expansão |
| `CONVERSATIONS_DIR` | `data/conversations` | Diretório .md das conversas |
| `SEARCH_TOP_K` | `3` | Resultados na busca |
| `SEARCH_BACKEND` | `ripgrep` | Backend padrão: ripgrep, bm25, fts5, hybrid |
| `SPACY_MODEL` | `pt_core_news_lg` | Modelo spaCy para query expansion |
| `VECTOR_DB_PATH` | `data/conversations/.vec.db` | Path do sqlite-vec |
| `EMBEDDING_DIM` | `300` | Dimensão dos embeddings (spaCy vectors) |
| `RRF_K` | `60` | Constante RRF para busca híbrida |
| `DB_PATH` | `data/memories.db` | Path do SQLite de memórias estruturadas |

## Notas técnicas

- O parser `_merge_parts` no OpenAIParser retorna conteúdo bruto incluindo metadata de áudio.
- `sanitize_title()` em `utils/filenames.py` é compartilhado entre `writer.py` e `mcp_server.py`.
- O MCP server usa estado global (`_session_id`, `_expander`) — lazy initialization.
- `pipeline/dataset.py` referencia `config.system_prompt` que não existe no `MemoryConfig` atual (será None via getattr).
- `db/store.py` valida scope e source com sets imutáveis (`_VALID_SCOPES`, `_VALID_SOURCES`).
- `search_hybrid.py` usa RRF fusion com `1/(k + rank)` para combinar BM25 + vector search.
- Os embeddings usam `nlp(text).vector` do spaCy — 300-dim, zero deps externas.

## Code style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
  Prefer names that return <5 grep hits in the codebase.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- No code duplication. Extract shared logic into a function/module.
- Early returns over nested ifs. Max 2 levels of indentation.
- Exception messages must include the offending value and expected shape.

## Comments

- Keep your own comments. Don't strip them on refactor — they carry
  intent and provenance.
- Write WHY, not WHAT. Skip `# increment counter` above `i++`.
- Docstrings on public functions: intent + one usage example.
- Reference issue numbers / commit SHAs when a line exists because
  of a specific bug or upstream constraint.

## Tests

- Tests run with: `uv run pytest`
- Every new function gets a test. Bug fixes get a regression test.
- Mock external I/O (API, DB, filesystem) with named fake classes,
  not inline stubs.
- Tests must be F.I.R.S.T: fast, independent, repeatable,
  self-validating, timely.

## Dependencies

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libs behind a thin interface owned by this project.

## Structure

- Follow the framework's convention (Typer CLI, etc.).
- Prefer small focused modules over god files.
- Predictable paths: cli/parsers/conversations/db/dataset/utils.

## Formatting

- Use `ruff` for formatting and linting. Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.
