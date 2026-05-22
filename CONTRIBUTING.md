# Contributing

## Setup

```bash
uv sync --group dev
uv run spacy download pt_core_news_lg
```

## Tests

```bash
uv run python -m pytest          # run all
uv run python -m pytest -x       # stop on first failure
uv run python -m pytest --cov    # with coverage
```

Every new function gets a test. Bug fixes get a regression test.

## Lint & Type Check

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/mem0ry
```

## Code Style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- Early returns over nested ifs. Max 2 levels of indentation.
- See `AGENTS.md` for full conventions.

## Adding a Parser

1. Create `src/mem0ry/parsers/<source>.py`
2. Subclass `BaseParser` from `parsers/base.py`
3. Implement `parse(source_dir) -> list[ParsedConversation]`
4. Register in `writer.py` auto-detection
5. Add tests in `tests/test_parser_<source>.py`

## Adding an MCP Tool

1. Add the tool function in `src/mem0ry/mcp_server.py`
2. Register with `@mcp.tool()` decorator
3. Add tests in `tests/test_mcp_server.py`

## PR Checklist

- [ ] Tests pass (`uv run python -m pytest`)
- [ ] Lint clean (`uv run ruff check .`)
- [ ] Types clean (`uv run mypy src/mem0ry`)
- [ ] No `print()` in library code — use `logging`
