# Testing

myMem0ry uses **pytest** with coverage reporting. The CI pipeline runs `ruff`, `mypy`, and `pytest --cov` on every push and PR.

## Running tests locally

```bash
# Full suite
uv run pytest

# With coverage
uv run pytest --cov --cov-report=term-missing

# Single file
uv run pytest tests/test_db_store.py

# Single test
uv run pytest tests/test_db_store.py::TestClass::test_thing

# By keyword
uv run pytest -k "test_default"
```

## Test organization

| Test file | Domain |
|---|---|
| `test_cli_main.py` | CLI command registration and root callback |
| `test_cli_conversation.py` | Conversation split, search, index commands |
| `test_cli_diagnostics.py` | `doctor`, `version`, `stats`, `projects` |
| `test_cli_hooks.py` | Hook path resolution and install |
| `test_cli_server.py` | `serve` command |
| `test_cli_expand.py` | Query expansion |
| `test_db_schema.py` | Schema initialization and version |
| `test_db_migrate.py` | Migration logic |
| `test_db_store.py` | Memory CRUD, search, stats, lifecycle |
| `test_db_connection.py` | SQLite connection + `sqlite-vec` loading |
| `test_mcp_server.py` | Core MCP tools |
| `test_mcp_server_extra.py` | Extended MCP behavior |
| `test_mcp_tools.py` | Tool-level integration tests |
| `test_web.py` | Web UI routes and handlers |
| `test_auth.py`, `test_auth_extra.py` | Auth middleware and token flow |
| `test_search_bm25.py`, `test_search_full.py` | Search backend correctness |
| `test_embeddings.py`, `test_encoders.py` | Vector encoder tests |
| `test_git_sync.py` | Git auto-sync logic |
| `test_git_context.py` | Git-based context resolution |
| `test_handoffs.py` | Handoff CRUD and acceptance |
| `test_hook_router.py` | Hook router event filtering |
| `test_retention.py` | Salience and decay logic |
| `test_evolution.py` | Memory evolution |
| `test_backup_restore.py` | Backup / restore round-trip |
| `test_export_import.py` | JSON export / import |
| `test_compression.py` | SmartCrusher compression |
| `test_daemon.py` | Daemon lifecycle and PID management |
| `test_dataset.py`, `test_pipeline_dataset.py` | Dataset builder pipeline |
| `test_vector_store.py` | sqlite-vec vector store |
| `test_observations.py`, `test_observability.py` | Observations and audit |
| `test_builder.py`, `test_writer.py`, `test_writer_extra.py` | ChatML builder and writers |
| `test_filenames.py` | Filename sanitization |
| `test_config.py` | Configuration defaults |
| `test_update_check.py` | Version check logic |
| `test_sonarqube_regression.py` | SonarQube rule compliance |

## CI pipeline

`.github/workflows/ci.yml`:

1. `uv sync --group dev`
2. `uv run ruff check .`
3. `uv run mypy src/mem0ry`
4. `uv run pytest --cov --cov-report=term-missing`

## Tips for future agents

- **Changing DB schema?** Add tests in `test_db_schema.py` and `test_db_migrate.py`, then run `test_db_store.py`.
- **Changing search?** Run `test_search_bm25.py`, `test_search_full.py`, `test_embeddings.py`, and `test_encoders.py`.
- **Changing MCP tools?** Run `test_mcp_server.py`, `test_mcp_server_extra.py`, and `test_mcp_tools.py`.
- **Changing web UI?** Run `test_web.py` and `test_auth.py`.
- **Changing retention?** Run `test_retention.py` and `test_evolution.py`.
- **Changing CLI?** Run the matching `test_cli_*.py` file.

All tests use temporary directories and in-memory or temp-file databases, so they are safe to run in parallel and do not mutate your real `data/` directory.
