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
│   ├── openai.py            # OpenAIParser — lê exports JSON do ChatGPT
│   └── gemini.py            # GeminiParser — lê exports JSON do Google Takeout
├── conversations/
│   ├── writer.py            # split_conversations() — export → .md por data (auto-detecta OpenAI/Gemini)
│   ├── search.py            # search() — busca via ripgrep
│   ├── search_bm25.py       # search_bm25() — busca via BM25 (rank-bm25)
│   ├── search_fts.py        # search_fts() — busca via SQLite FTS5
│   ├── query_expansion.py   # ConceptSearch + expand_query — expansão semântica via FFN walk (cache em disco)
│   └── benchmark.py         # run_benchmark() — compara backends
├── dataset/                 # Pipeline legado de fine-tuning (builder, temporal, splitter, etc.)
└── pipeline/dataset.py      # Dataset JSONL legado
```

## Comandos CLI

```bash
# Pipeline de conversas
mymem0ry split                        # Export (OpenAI/Gemini) → .md por data em data/conversations/
mymem0ry search "qdrant"              # Busca em conversas (ripgrep, bm25 ou fts5)
mymem0ry search "qdrant" --expand     # Busca com expansão semântica da query
mymem0ry benchmark "python"           # Compara backends lado a lado
mymem0ry benchmark "python" --expand  # Benchmark com query expansion
mymem0ry warmup                       # Pré-carrega modelo e cacheia embeddings
mymem0ry index                        # Constrói índices BM25 e FTS5
mymem0ry dataset                      # Build ChatML JSONL (legacy)
```

## Query Expansion

O flag `--expand` usa FFN walk (estilo LARQL) para encontrar conceitos semanticamente relacionados. Ao invés de cosine similarity na embedding matrix (superficial), faz gate KNN nas camadas FFN do modelo — acessa o conhecimento semântico real armazenado nos pesos.

O cache FFN (gate_projs + feature-to-token lookup) é construído com `mymem0ry warmup` e fica em `data/.cache/ffn/`. Se não há cache FFN, faz fallback pra embedding similarity.

### Camadas FFN

O warmup aceita `--layers` para definir o range de camadas FFN a cachear:
```bash
mymem0ry warmup                     # default: L20-35
mymem0ry warmup -l 18-32            # custom range
```

**Importante**: camadas do meio guardam conhecimento semântico (relações entre conceitos). Camadas finais (últimas ~5) estão na fase de predição de tokens e produzem resultados pobres. Regra prática:

| Modelo | Total layers | Banda recomendada |
|--------|-------------|-------------------|
| Gemma 4B | 42 | L18-L32 |
| Gemma 2B | 26 | L12-L20 |
| Qwen 0.5B | 24 | L10-L18 |

Fluxo:
1. Tokeniza a query
2. Computa embedding médio dos tokens
3. Para cada camada cacheada: gate KNN (quais features ativam) → lookup de tokens relacionados
4. Agrega resultados por score, filtra stop words e duplicatas
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
├── Gemini/                     # JSONs de export do Google Takeout (Minhaatividade.json)
├── conversations/YYYY-MM-DD/   # Conversas individuais em .md (gerado por split, ambas fontes)
└── .cache/                     # Cache gerado por warmup
    ├── embeddings/<model>/     # Embedding matrix + tokenizer (fallback)
    └── ffn/<model>/            # FFN walk: gate_projs + feature_tokens (~850 MB)
```

## Notas técnicas

- O parser `_merge_parts` no OpenAIParser retorna conteúdo bruto incluindo metadata de áudio. Conversas de texto são limpas; as de voz vêm com dicts JSON inline.
- Os testes usam pytest. Linter: ruff.
