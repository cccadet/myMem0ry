# Backends de busca

Múltiplos backends para indexação e busca; vivem em `src/mem0ry/conversations/`.

## Backends

| Backend | Onde | Quando usar |
|---|---|---|
| **ripgrep** (default) | `conversations/search.py` | Busca simples em `.md` arquivados. Requer `rg` no PATH. |
| **BM25** | `conversations/search_bm25.py` | Ranking lexical clássico; sem semântica. |
| **FTS5** | `conversations/search_fts.py` | SQLite FTS5 nativo; rápido, suportado em qualquer SQLite. |
| **vector (sqlite-vec)** | `conversations/vector_store.py` | Semântico via embeddings spaCy. |
| **hybrid** | `conversations/search_hybrid.py` | RRF fusion: BM25 + vector. **1/(k + rank)**, k=60. |

## Embeddings

- `conversations/embeddings.py:SpacyEncoder` — `nlp(text).vector`, 300 dim.
- `EMBEDDING_DIM=300` em `config.py`. **Deve casar** com o modelo spaCy.
- Trocar de modelo spaCy sem ajustar `EMBEDDING_DIM` → embeddings corrompidos.

## Expansão semântica

- `conversations/spacy_expand.py:SpacyConceptSearch` — expande query com tokens semanticamente relacionados (vetores spaCy).
- `EXPAND_TOP_K=10` (env).

## Defaults (env)

- `SEARCH_BACKEND=ripgrep` (default mais simples).
- `SEARCH_TOP_K=3` (resultados por busca).
- `RRF_K=60` (constante de fusão).

## Comandos

```bash
mymem0ry search "query"                          # ripgrep
mymem0ry search "query" --backend hybrid --expand   # RRF + expansão
mymem0ry search "query" --backend bm25
mymem0ry search "query" --backend fts
mymem0ry index                                   # constrói BM25 + FTS5 + vector
mymem0ry benchmark "query"                       # compara backends
mymem0ry expand "token"                          # tokens relacionados
```

## Dependência crítica: ripgrep

- `ripgrep` (`rg`) **deve** estar no PATH.
- `bin/setup` checa no bootstrap.
- CI não cobre — se faltar `rg`, o backend ripgrep falha em runtime.

## When editing…

- **Novo backend**: subclasse em `conversations/search_*.py`; registrar em `cli/main.py` (escolha do `--backend`).
- **Bug "busca ruim"**: rodar `mymem0ry benchmark "query"` para comparar.
- **Modelo spaCy trocado**: ajustar `EMBEDDING_DIM` no `.env` + `mymem0ry index` (reindex obrigatório).
- **Performance ruim**: FTS5 + BM25 cobrem a maioria. Vector vale para queries conceituais ("como o sistema decide X").
- **Mexer em `SpacyEncoder`**: o modelo spaCy é carregado lazy (custo de ~5s); cache em global se for usado frequentemente.
