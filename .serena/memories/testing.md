# Testes

## Conftest

- `tests/conftest.py:3` define `MEM0RY_NO_UPDATE_CHECK=1` — silencia o update check da CLI durante testes. **Não remover** — suja o stdout do pytest.

## Fixtures

- **Sem fixtures compartilhadas** além de env vars. Cada arquivo de teste cria o que precisa localmente.
- DBs temporários: `test_db_store.py`, `test_handoffs.py`, `test_observations.py` têm `@pytest.fixture` próprio com `tmp_path`.

## Cobertura

- `fail_under = 80` em `pyproject.toml:81` — CI quebra abaixo.
- Rodar: `uv run python -m pytest --cov`.

## Mutação

- `mutmut` configurado em `pyproject.toml:83-87`.
- Rodar: `uv run mutmut run`.
- Scope: `src/mem0ry` (exclui `test_*` e `__init__.py`).

## Suites pesadas

- `tests/test_sonarqube_regression.py` é **lenta**. Pular durante iteração: `pytest -k "not sonarqube"`.

## Ordem do CI (de `.github/workflows/ci.yml`)

1. `uv run ruff check .`
2. `uv run mypy src/mem0ry` (mypy.ini tem `ignore_missing_imports` para `spacy`, `sqlite-vec`, `rank_bm25`)
3. `uv run python -m pytest --cov` (com coverage)

## Shortcuts

```bash
uv run pytest tests/test_db_store.py                          # 1 arquivo
uv run pytest tests/test_db_store.py::TestClass::test_thing    # 1 teste
uv run pytest -k "test_default"                                # match por nome
uv run pytest -x                                                # parar no 1º fail
```

## When editing…

- **Nova tool MCP**: adicionar teste de registro em `tests/test_mcp_server.py` (já tem guard).
- **Novo módulo em `src/mem0ry/`**: garantir cobertura ≥80%. Se cai abaixo, pytest falha.
- **Migration nova**: testar com DB na versão anterior (script/seed) e bump.
- **Test que precisa de DB limpo**: usar `tmp_path` fixture; nunca tocar `data/` real.
- **Test lento**: considerar marker `@pytest.mark.slow` + skip em CI rápido.
