# AGENTS.md — myMem0ry

Sistema de busca pessoal em conversas com query expansion semântica (spaCy).

## Stack

- Python 3.11+, uv, Typer CLI
- spaCy (word vectors pt_core_news_lg para query expansion)
- ripgrep, rank-bm25, SQLite FTS5 (busca em conversas)
- MCP (FastMCP) para servidor de memória

## Estrutura

```
src/mem0ry/
├── __init__.py               # Exporta CLI app
├── config.py                 # MemoryConfig dataclass
├── mcp_server.py             # MCP server — 5 tools + 2 prompts
├── cli/main.py               # Typer CLI — split, search, benchmark, expand, index, dataset
├── parsers/
│   ├── base.py               # ParsedConversation, ParsedMessage, BaseParser ABC
│   ├── openai.py             # OpenAIParser — ChatGPT JSON exports (mapping tree)
│   └── gemini.py             # GeminiParser — Google Takeout JSON (safeHtmlItem)
├── conversations/
│   ├── writer.py             # split_conversations() — export → .md por data
│   ├── search.py             # search() — ripgrep backend
│   ├── search_bm25.py        # search_bm25() — BM25Okapi
│   ├── search_fts.py         # search_fts() — SQLite FTS5
│   ├── spacy_expand.py       # SpacyConceptSearch + expand_query_spacy
│   └── benchmark.py          # run_benchmark() — compara backends
├── dataset/                  # Pipeline legado de fine-tuning ChatML
│   ├── builder.py            # build_chatml_examples()
│   ├── temporal.py           # format_timestamp(), enrich_conversations()
│   ├── filter.py             # apply_quality_filters()
│   ├── dedupe.py             # deduplicate_examples() — SHA256
│   ├── splitter.py           # train_val_split()
│   └── stats.py              # compute_stats()
├── pipeline/
│   └── dataset.py            # build_dataset_from_openai() — JSONL pipeline
└── utils/
    ├── filenames.py          # sanitize_title() — shared filename cleaning
    ├── logging.py            # configure_logging()
    └── paths.py              # ensure_dir()
```

## Comandos CLI

```bash
mymem0ry split                        # Export (OpenAI/Gemini) → .md por data
mymem0ry search "qdrant"              # Busca (ripgrep default)
mymem0ry search "qdrant" --expand     # Busca com expansão spaCy
mymem0ry benchmark "python"           # Compara backends
mymem0ry expand "france"              # Tokens semanticamente relacionados
mymem0ry index                        # Constrói índices BM25 + FTS5
mymem0ry dataset                      # Build ChatML JSONL (legacy)
```

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
| `SEARCH_BACKEND` | `ripgrep` | Backend padrão: ripgrep, bm25, fts5 |
| `SPACY_MODEL` | `pt_core_news_lg` | Modelo spaCy para query expansion |

## Notas técnicas

- O parser `_merge_parts` no OpenAIParser retorna conteúdo bruto incluindo metadata de áudio.
- `sanitize_title()` em `utils/filenames.py` é compartilhado entre `writer.py` e `mcp_server.py`.
- O MCP server usa estado global (`_session_id`, `_expander`) — lazy initialization.
- `pipeline/dataset.py` referencia `config.system_prompt` que não existe no `MemoryConfig` atual (será None via getattr ou precisa ser adicionado).

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
- Predictable paths: cli/parsers/conversations/dataset/utils.

## Formatting

- Use `ruff` for formatting and linting. Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.
