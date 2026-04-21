# CLAUDE.md — myMem0ry

Sistema de busca pessoal em conversas com query expansion semântica.

## Stack

- Python 3.13, uv, Typer CLI
- spaCy (word vectors para query expansion)
- ripgrep, rank-bm25, SQLite FTS5 (busca em conversas)

## Estrutura

```
src/mem0ry/
├── cli/main.py              # Typer CLI — todos os comandos
├── config.py                # MemoryConfig dataclass
├── parsers/
│   ├── base.py              # ParsedConversation, ParsedMessage, BaseParser
│   ├── openai.py            # OpenAIParser — lê exports JSON do ChatGPT
│   └── gemini.py            # GeminiParser — lê exports JSON do Google Takeout
├ conversations/
│   ├── writer.py            # split_conversations() — export → .md por data (auto-detecta OpenAI/Gemini)
│   ├── search.py            # search() — busca via ripgrep
│   ├── search_bm25.py       # search_bm25() — busca via BM25 (rank-bm25)
│   ├── search_fts.py        # search_fts() — busca via SQLite FTS5
│   ├── spacy_expand.py      # SpacyConceptSearch + expand_query_spacy — expansão semântica via spaCy word vectors
│   └── benchmark.py         # run_benchmark() — compara backends
├── dataset/                 # Pipeline legado de fine-tuning (builder, temporal, splitter, etc.)
└── pipeline/dataset.py      # Dataset JSONL legado
```

## Comandos CLI

```bash
# Pipeline de conversas
mymem0ry split                        # Export (OpenAI/Gemini) → .md por data em data/conversations/
mymem0ry search "qdrant"              # Busca em conversas (ripgrep, bm25 ou fts5)
mymem0ry search "qdrant" --expand     # Busca com expansão semântica (spaCy)
mymem0ry benchmark "python"           # Compara backends lado a lado
mymem0ry benchmark "python" --expand  # Benchmark com query expansion
mymem0ry index                        # Constrói índices BM25 e FTS5
mymem0ry expand "france"              # Top-10 tokens semanticamente relacionados
mymem0ry dataset                      # Build ChatML JSONL (legacy)
```

## Query Expansion

O flag `--expand` usa spaCy word vectors para encontrar palavras semanticamente relacionadas. Operação ao nível de palavras (sem fragmentação BPE/subword). Usa uma matriz normalizada de todo o vocabulário para cosine similarity rápida.

### Comando expand

```bash
mymem0ry expand "france"             # top-10 tokens relacionados
mymem0ry expand "france" -k 20       # mais resultados
```

Fluxo:
1. Processa a query com spaCy NLP
2. Computa vetor médio dos tokens com vetor
3. Cosine similarity contra toda a matriz de vocabulário normalizada
4. Filtra palavras da query e variantes morfológicas (prefixo compartilhado de 4 chars)
5. Expande a query original com os termos encontrados
6. Passa a query expandida ao backend de busca (ripgrep/bm25/fts5)

## Configuração

Variáveis de ambiente (ou `.env` na raiz do projeto):

| Variável | Default | Uso |
|---|---|---|
| `EXPAND_TOP_K` | `10` | Quantos tokens similares gerar |
| `CONVERSATIONS_DIR` | `data/conversations` | Diretório das conversas em .md |
| `SEARCH_TOP_K` | `3` | Quantos arquivos recuperar na busca |
| `SEARCH_BACKEND` | `ripgrep` | Backend padrão: ripgrep, bm25, fts5 |
| `SPACY_MODEL` | `pt_core_news_lg` | Modelo spaCy para query expansion |

## Dados

```
data/
├── openai/export/              # JSONs de export do ChatGPT (fonte original)
├── gemini/                     # JSONs de export do Google Takeout (Minhaatividade.json)
└── conversations/YYYY-MM-DD/   # Conversas individuais em .md (gerado por split, ambas fontes)
```

## Notas técnicas

- O parser `_merge_parts` no OpenAIParser retorna conteúdo bruto incluindo metadata de áudio. Conversas de texto são limpas; as de voz vêm com dicts JSON inline.
- Os testes usam pytest. Linter: ruff.
