# CLAUDE.md — myMem0ry

Sistema de memória pessoal usando KV Cache — sem fine-tuning, sem vector store.

## Stack

- Python 3.13, uv, Typer CLI
- transformers + torch (inferência GPU/CPU)
- OpenAI SDK (extração de memórias via Ollama ou OpenAI API)
- ripgrep (busca em conversas)

## Estrutura

```
src/mem0ry/
├── cli/main.py          # Typer CLI — todos os comandos
├── config.py            # MemoryConfig dataclass
├── parsers/
│   ├── base.py          # ParsedConversation, ParsedMessage, BaseParser
│   └── openai.py        # OpenAIParser — lê exports JSON do ChatGPT
├── conversations/
│   ├── writer.py        # split_conversations() — export → .md por data
│   ├── search.py        # search() — busca via ripgrep
│   └── ask.py           # ask() — busca + inferência direta
├── kvcache/
│   ├── cache.py         # save_kv / load_kv — serialização do cache
│   ├── extract.py       # extract_memories() — LLM extrai fatos das conversas
│   └── model.py         # load_model, build_cache, chat
├── dataset/             # Pipeline legado de fine-tuning (builder, temporal, splitter, etc.)
└── pipeline/dataset.py  # Dataset JSONL legado
```

## Comandos CLI

```bash
# Pipeline de memórias (fluxo original)
mymem0ry build                    # Parse + extrai memórias → memories.txt
mymem0ry build-cache              # memories.txt → KV cache serializado
mymem0ry chat "pergunta"          # Chat usando KV cache pré-construído
mymem0ry interactive              # Modo interativo

# Pipeline de conversas (fluxo novo)
mymem0ry split                    # Export OpenAI → .md por data em data/conversations/
mymem0ry ask "qdrant"             # Busca ripgrep → contexto → inferência direta
```

## Fluxo `ask` (busca + resposta)

1. `ripgrep` busca a query nos arquivos `.md` de `data/conversations/YYYY-MM-DD/`
2. Carrega conteúdo dos top-K arquivos (default 3, config `search_top_k`)
3. Monta prompt ChatML com contexto + pergunta
4. Inferência em único forward pass (sem cache serializado)
5. Retorna resposta do modelo

## Configuração

Variáveis de ambiente (ou `.env` na raiz do projeto):

| Variável | Default | Uso |
|---|---|---|
| `EXTRACTION_BACKEND` | `ollama` | `ollama` ou `openai` |
| `OLLAMA_MODEL` | `qwen3.5:0.8b` | Modelo para extração de memórias |
| `KVCACHE_MODEL` | `Qwen/Qwen3.5-0.8B` | Modelo para inferência/cache |
| `KVCACHE_MAX_TOKENS` | `1024` | Limite de tokens no cache/prompt |
| `CONVERSATIONS_DIR` | `data/conversations` | Diretório das conversas em .md |
| `SEARCH_TOP_K` | `3` | Quantos arquivos recuperar na busca |

## Dados

```
data/
├── openai/export/              # JSONs de export do ChatGPT (fonte original)
├── conversations/YYYY-MM-DD/   # Conversas individuais em .md (gerado por split)
└── memories/                   # memories.txt extraído (gerado por build)
```

## Notas técnicas

- Qwen 3.5 usa arquitetura híbrida (linear + standard attention). O `build-cache` pré-computa cache serializado que funciona com modelos de attention padrão. Para Qwen 3.5, o comando `ask` faz inferência direta em vez de injetar cache pré-construído.
- O parser `_merge_parts` no OpenAIParser retorna conteúdo bruto incluindo metadata de áudio. Conversas de texto são limpas; as de voz vêm com dicts JSON inline.
- Os testes usam pytest. Linter: ruff.
