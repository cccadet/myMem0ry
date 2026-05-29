# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.14.9] - 2026-05-29

### Fixed

- **MCP tool timeouts on Windows (root cause).** Tools that resolve git context
  (`get_context`, `search_memory`, `save_memory`, etc.) deadlocked indefinitely when
  the server runs over stdio. The `git` subprocess inherited the server's stdio pipe
  handles, so it never returned. `_git` now spawns with `stdin=DEVNULL` and
  `CREATE_NO_WINDOW`, eliminating handle inheritance. `get_context` went from an
  infinite hang (>25s timeout) to ~0.35s.

### Changed

- `init_schema` now gates on `PRAGMA user_version` and skips all DDL when the schema
  is already current, removing write-lock contention from every tool call.
- `track_reads` runs on a daemon thread so read-path tools (`get_context`,
  `search_memory`) no longer block on access-count writes.
- `ensure_server` health-checks before spawning, so a running server with a stale or
  missing PID file no longer spawns a ghost process that fails on a port conflict.
- MCP server startup deferred spaCy and auth imports and runs `ensure_server` in a
  background thread, cutting stdio cold-start from ~5.7s to ~3.6s.

## [0.14.7] - 2026-05-29

### Added

- Web UI: **Handoffs page** (`/handoffs`) — lists all handoffs with status filter tabs
  (All / Open / Accepted / Expired), showing ID, status badge, from-agent, project,
  summary preview and created date.
- Web UI: **Handoff detail page** (`/handoff/{id}`) — shows full summary, open questions,
  next steps, acceptance metadata and all fields. Links resolve correctly from the audit log.
- Web UI: "Handoffs" nav link added between Projects and Search.
- Dashboard: "open handoffs" stat is now a clickable link to `/handoffs?status=open`.
- `mymem0ry hooks --config` now includes the `SessionEnd` hook in the generated
  `settings.json` snippet so new installs wire it up automatically.

### Fixed

- `SessionEnd` hook was never registered in the Claude Code `settings.json` config output,
  so `session-end.sh` (which already existed in the package) was never fired — session-end
  observations, conversation archiving and auto-handoff creation were all silently skipped.

## [0.14.6] - 2026-05-28

### Fixed

- `memory_handoff_begin` was missing its `@mcp.tool()` decorator, so it was never
  registered as an MCP tool — agents could not create handoffs. This is the core of the
  cross-agent workflow.
- Claude Code hook scripts fabricated a per-invocation `session_id` (`date | md5sum`),
  so observations never grouped under one session and the auto-handoff on session end
  found nothing to summarize. Hooks now read the real `session_id`, `cwd`, and
  `transcript_path` from the stdin payload.

### Added

- `read_memory` MCP tool: fetch the full content of a memory by the `path` returned by
  `search_memory` (which only returns previews). Includes path-traversal protection.
- `session-end` now archives the full conversation with zero LLM tokens when the hook
  forwards `transcript_path` — the server parses the transcript instead of relying on
  inlined `messages`. `ClaudeCodeParser` now accepts live-transcript `type: "user"`
  entries (previously only `"human"`).
- `docs/usage.md`: "Switching harness mid-task" end-to-end guide.

## [0.14.5] - 2026-05-28

### Fixed

- `save_memory` without `cwd`: `_resolve_cwd` now falls back to `Path.cwd()` instead of
  returning `project_id=None`. Previously, memories saved with `scope="project"` but no
  `cwd` argument would have `project_id=NULL`, causing the projects count in the dashboard
  to show 0.
- Warning log added when `scope` is `project` or `context` but `project_id` resolves to `None`,
  making it easier to diagnose misconfigured agents.

## [0.14.4] - 2026-05-28

### Fixed

- `/hook` endpoint now processes events in a background thread, returning 202 immediately.
  Previously, synchronous processing blocked the single-threaded uvicorn server, causing
  `save_memory` and other MCP tool calls to hang while waiting for DB locks.
- All DB operations now use `try/finally` to guarantee connection cleanup, preventing
  leaked connections from holding SQLite write locks.
- Hook error isolation: failures in conversation archiving, session-end, or auto-handoff
  no longer prevent the observation from being recorded.

## [0.14.3] - 2026-05-28

### Fixed

- SQLite busy timeout added (15s) to prevent lock contention between concurrent
  hooks, MCP tools, and web UI requests. Previously, the default 5s timeout could
  cause `save_memory` and other writes to hang indefinitely under concurrent access.

## [0.14.2] - 2026-05-28

### Fixed

- Audit log links for observations now point to `/observation/{id}` instead of `/memory/{id}`,
  which caused "Memory not found" errors. New observation detail page added to the web UI.

## [0.14.1] - 2026-05-28

### Fixed

- `mymem0ry hooks --config` now generates correct JSON format for Claude Code hooks
  (wraps each command in `{"type": "command", "command": "..."}` array)

## [0.14.0] - 2026-05-28

### Added

- `mymem0ry hooks` — new CLI command: `--path` prints hooks directory, `--config` prints
  settings.json snippet, `--install` copies hooks for detected agent
- Hooks now included in PyPI wheel (force-include in hatchling)
- Updated docs across README, install guide, usage guide — all use `mymem0ry hooks --config`

## [0.13.0] - 2026-05-27

### Added

- PyPI release. No code changes.

## [0.12.2] - 2026-05-27

### Fixed

- MCP stdio transport nunca rodava `mcp.run()` — apenas iniciava o daemon HTTP e o processo encerrava, fazendo o Claude Code reportar "MCP failed to start". Agora a branch stdio sobe o daemon e roda o loop MCP stdio em sequência.

## [0.3.0] - 2026-05-21

### Added

- `mymem0ry doctor` — verifica saude do sistema (spaCy, sqlite-vec, DB, indices)
- Busca hibrida com RRF fusion (BM25 + vector via `--backend hybrid`)
- Comando `mymem0ry benchmark` — compara backends lado a lado
- Comando `mymem0ry index` — constroi indices BM25, FTS5 e vector
- Comando `mymem0ry migrate` — migra .md existentes para SQLite estruturado
- Comando `mymem0ry stats` — overview da base de memorias
- Comando `mymem0ry projects` — lista projectos com memorias
- MCP server com 9 tools: log_message, save_memory, save_conversation, read_memory, search_memory, get_context, list_scopes, end_session, memory_stats
- 2 MCP prompts: auto_save_instructions, conversation_logger
- Escopos de memoria: global, project, session
- Parser para Claude Code (.jsonl) e Claude Export (.json)
- Parser para Gemini (Google Takeout)
- Parser para OpenAI (ChatGPT JSON exports)
- Embeddings locais com spaCy word vectors (300-dim)
- Vector store com sqlite-vec
- Query expansion semantica com spaCy (`--expand`)
- Logging estruturado em JSON (`utils/logging.py`)
- CI com GitHub Actions (ruff, mypy, pytest --cov)
- CHANGELOG.md e CONTRIBUTING.md

### Changed

- Logging substitui `print()` em search_bm25.py e benchmark.py
- Versao bumpada de 0.2.0 para 0.3.0

### Removed

- Dependencia `openai>=1.0` (nao utilizada)

## [0.2.0] - 2026-04-01

### Added

- Parser para OpenAI ChatGPT JSON exports (mapping tree)
- Parser para Gemini Google Takeout JSON
- Comando `mymem0ry split` — converte exports em .md por data
- Busca com ripgrep (default), BM25, FTS5
- Comando `mymem0ry expand` — tokens semanticamente relacionados
- Configuracao via variaveis de ambiente
- 245 testes

[Unreleased]: https://github.com/cccadet/myMem0ry/compare/v0.14.5...HEAD
[0.14.5]: https://github.com/cccadet/myMem0ry/compare/v0.14.4...v0.14.5
[0.14.4]: https://github.com/cccadet/myMem0ry/compare/v0.14.3...v0.14.4
[0.14.3]: https://github.com/cccadet/myMem0ry/compare/v0.14.2...v0.14.3
[0.14.2]: https://github.com/cccadet/myMem0ry/compare/v0.14.1...v0.14.2
[0.14.1]: https://github.com/cccadet/myMem0ry/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/cccadet/myMem0ry/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/cccadet/myMem0ry/releases/tag/v0.13.0
[0.12.2]: https://github.com/cccadet/myMem0ry/compare/v0.3.0...v0.12.2
[0.2.0]: https://github.com/cccadet/myMem0ry/releases/tag/v0.2.0
