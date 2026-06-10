# Gotchas e config

Armadilhas que mordem sem aviso. Coletadas em uma página.

## `config.py` carrega `.env` no import

- `from mem0ry.config import MemoryConfig` → `load_dotenv()` roda **na importação do módulo**.
- Testes que dependem de env: usar `monkeypatch.setenv` **antes** de importar, OU `tmp_path` com `.env` próprio.
- Reimportar não relê o `.env` (cache do módulo).

## `_default_data_dir` muda com install

- `config.py:17` decide o data dir:
  - **Dev install** (uv sync): `<project_root>/data/`.
  - **Site-packages** (pip install -e não, pip install sim): `~/.local/share/mem0ry` (Linux) ou `%APPDATA%\mem0ry` (Windows).
- Consequência: `data/` do repo pode sumir quando o pacote é instalado; comandos que esperam `data/` quebram.
- `data/` é **gitignored** — DBs (`memories.db`, `.vec.db`) e spool são criados em runtime.

## Globals no MCP server

- `_session_id` e `_expander` (`SpacyConceptSearch`) em `mcp_server.py` são **module-level**.
- **Não thread-safe**; reset requer reinício do processo.
- Assumido: 1 cliente MCP por processo.

## Lazy creation

- `data/` é criado na **primeira conexão** com DB, não na instalação.
- Se o teste assume que `data/` existe antes de qualquer operação, vai falhar — criar antes.

## Stubs vazios

- `src/mem0ry/pipeline/` e `src/mem0ry/training/` existem na árvore mas estão **vazios**.
- Ignorar a menos que esteja estendendo o pipeline de fine-tuning.

## Mypy `ignore_missing_imports`

- Em `mypy.ini`: `spacy`, `sqlite-vec`, `rank_bm25`.
- Essas libs não têm stubs públicos; mypy aceita sem checar tipos delas.
- Não é desculpa para `Any` no **seu** código — só relaxa imports externos.

## `EMBEDDING_DIM=300` deve casar com o modelo spaCy

- `en_core_web_lg` e `pt_core_news_lg` produzem vetores de 300 dim.
- Trocar de modelo spaCy exige `EMBEDDING_DIM` no `.env` e **reindex** (`mymem0ry index`).

## When editing…

- **Test que precisa de env isolado**: `monkeypatch.setenv` **antes** de importar, ou criar `tmp_path/.env` e patchar `dotenv_path`.
- **Mexer em `config.py`**: lembrar que é importado em toda parte — mudanças no path de `data_dir` quebram workflows.
- **Adicionar dep sem tipos**: adicionar a `mypy.ini` ignore (se sumir o `ignore_missing_imports`, mypy reclama).
- **Debug "path errado"**: rodar `mymem0ry doctor` — health check mostra data dir, env, model.
- **Reindex após mudar embedding**: `mymem0ry index` (constrói BM25 + FTS5 + vector).
