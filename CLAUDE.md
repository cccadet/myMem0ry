# CLAUDE.md — myMem0ry

Sistema de busca pessoal em conversas com query expansion semântica.

## Stack

- Python 3.13, uv, Typer CLI
- transformers + torch (embeddings para query expansion)
- ripgrep, rank-bm25, SQLite FTS5 (busca em conversas)

## Estrutura

```
src/mem0ry/
├── cli/main.py              # Typer CLI — todos os comandos
├── config.py                # MemoryConfig dataclass
├── parsers/
│   ├── base.py              # ParsedConversation, ParsedMessage, BaseParser
│   └── openai.py            # OpenAIParser — lê exports JSON do ChatGPT
├── conversations/
│   ├── writer.py            # split_conversations() — export → .md por data
│   ├── search.py            # search() — busca via ripgrep
│   ├── search_bm25.py       # search_bm25() — busca via BM25 (rank-bm25)
│   ├── search_fts.py        # search_fts() — busca via SQLite FTS5
│   ├── query_expansion.py   # ConceptSearch + expand_query — expansão semântica via embeddings
│   └── benchmark.py         # run_benchmark() — compara backends
├── dataset/                 # Pipeline legado de fine-tuning (builder, temporal, splitter, etc.)
└── pipeline/dataset.py      # Dataset JSONL legado
```

## Comandos CLI

```bash
# Pipeline de conversas
mymem0ry split                        # Export OpenAI → .md por data em data/conversations/
mymem0ry search "qdrant"              # Busca em conversas (ripgrep, bm25 ou fts5)
mymem0ry search "qdrant" --expand     # Busca com expansão semântica da query
mymem0ry benchmark "python"           # Compara backends lado a lado
mymem0ry benchmark "python" --expand  # Benchmark com query expansion
mymem0ry index                        # Constrói índices BM25 e FTS5
mymem0ry dataset                      # Build ChatML JSONL (legacy)
```

## Query Expansion

O flag `--expand` usa a embedding matrix de um modelo de linguagem para encontrar tokens semanticamente similares ao termo pesquisado. A query original é expandida com esses tokens antes de ser passada ao backend de busca escolhido.

Fluxo:
1. Tokeniza a query
2. Computa embedding médio dos tokens
3. Calcula cosine similarity com todos os tokens do vocabulário
4. Seleciona os top-k tokens mais similares (filtrando stop words e duplicatas)
5. Expande a query original com os termos encontrados
6. Passa a query expandida ao backend de busca (ripgrep/bm25/fts5)

## Configuração

Variáveis de ambiente (ou `.env` na raiz do projeto):

| Variável | Default | Uso |
|---|---|---|
| `MODEL_NAME` | `Qwen/Qwen3.5-0.8B` | Modelo para query expansion |
| `EXPAND_TOP_K` | `10` | Quantos tokens similares gerar |
| `CONVERSATIONS_DIR` | `data/conversations` | Diretório das conversas em .md |
| `SEARCH_TOP_K` | `3` | Quantos arquivos recuperar na busca |
| `SEARCH_BACKEND` | `ripgrep` | Backend padrão: ripgrep, bm25, fts5 |

## Dados

```
data/
├── openai/export/              # JSONs de export do ChatGPT (fonte original)
└── conversations/YYYY-MM-DD/   # Conversas individuais em .md (gerado por split)
```

## Notas técnicas

- O parser `_merge_parts` no OpenAIParser retorna conteúdo bruto incluindo metadata de áudio. Conversas de texto são limpas; as de voz vêm com dicts JSON inline.
- Os testes usam pytest. Linter: ruff.
