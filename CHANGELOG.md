# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.17.0] - 2026-06-01

### Added

- **Update check** — on every CLI invocation, myMem0ry queries PyPI (cached 24h)
  and prints a yellow warning when a newer version is available:
  `myMem0ry 0.17.1 is available (you have 0.17.0). Run: uv tool upgrade myMem0ry`.
  Disable with `MEM0RY_NO_UPDATE_CHECK=1`.
- **Prerequisites section** in README — documents `uv`, `ripgrep`, and `git`
  with install commands for Linux, macOS, and Windows.

### Changed

- Renamed `auto_save_instructions()` → `mymem0ry_memory_instructions()` for
  clarity and consistency with the project name.

### Fixed

- Resolved 9 SonarQube issues:
  - **S1192**: Extracted duplicated SQL literal into `_SET_VERSION_SQL` constant
    in `db/migrate.py`.
  - **S3776**: Reduced cognitive complexity of `_extract_session_signals()` by
    extracting `_collect_unique()` helper in `db/store_handoffs.py`.
  - **S5713**: Removed redundant `urllib.error.URLError` from exception handlers
    (subclass of `OSError`) in `daemon.py`.
  - **S6019**: Fixed reluctant quantifier `+?` → `+` in `_ERROR_RE` regex.
  - **S6709**: Added seed `42` to `np.random.default_rng()` in `test_embeddings.py`.
  - **S100**: Renamed `test_windows_uppercase_USERS_dir` → `test_windows_uppercase_users_dir`
    and `test_filePath_variant` → `test_file_path_variant`.
  - **F401**: Removed unused `begin_handoff` import in `test_sonarqube_regression.py`.
- Added `tests/conftest.py` to suppress update check during tests.

## [0.16.0] - 2026-05-29

### Added

- **Fact evolution** — new `evolve_fact` MCP tool that lets the agent LLM
  consolidate contradictory or outdated facts without heuristics. When a user
  corrects previous information (e.g. "I migrated from Spark to Iceberg"), the
  agent calls `evolve_fact(old_ids=[...], evolved_content="...", rationale="...")`
  which soft-deletes old facts and creates a consolidated evolved fact.
- Schema v7: `superseded_by` column on the `memories` table tracks the evolution
  chain. Old facts are soft-deleted and hidden from `get_context()` and
  `search_memories()` but remain in the DB for audit.
- `migrate_v6_to_v7()` — adds `superseded_by` column and index.
- Web UI: "evolved facts" counter on dashboard, superseded badge on memory cards,
  "Supersedes" / "Superseded by" links on memory detail page.
- `auto_save_instructions` prompt now includes "Fact Evolution" section.
- 13 new tests in `test_evolution.py` + 2 regression tests in `test_db_store.py`.

### Changed

- `get_context()` and `search_memories()` now exclude superseded memories
  (`superseded_by IS NOT NULL`).
- AGENTS.md updated: schema v7, 11 MCP tools, fact evolution docs.

## [0.15.5] - 2026-05-29

### Fixed

- Fixed Changelog URL in `pyproject.toml` — changed `blob/main/` to
  `blob/master/` to match the repository's default branch.

## [0.15.4] - 2026-05-29

### Fixed

- Resolved 31 SonarQube issues (Quality Gate security rating now passes):
  - **S1854**: Removed unused `ensure_server` import in `mcp_server.py`.
  - **S6019**: Fixed reluctant quantifier in `_ERROR_RE` regex — changed
    `(?:;|$)` to `(?=;|$)` (lookahead) so errors at end-of-string are
    captured correctly.
  - **S5869**: Simplified duplicate character class `[A-Za-z]` → `[A-Z]`
    with `re.IGNORECASE` in `_WIN_HOME_PATTERN` (Windows home path stripping
    unchanged for all drive letter cases and forward/backslash variants).
  - **S1172**: Removed unused `days_threshold` parameter from `decay_memories`
    and renamed `request` → `_request` in Starlette page handlers.
  - **S5713**: Removed redundant exception subclasses already caught by
    `OSError` (`PermissionError`, `ProcessLookupError`, `FileNotFoundError`,
    `TimeoutExpired`, `URLError`) in `daemon.py`, `server.py`, and
    `git_context.py`.
  - **S1192**: Extracted `_DB_FILENAME` constant in `config.py` and
    `_CONFIG_DIR` constant in `cli/hooks.py` to eliminate string duplication.
    Added `_PKG_NAME` constant in `bin/install.sh`.
  - **S6711**: Replaced legacy `numpy.random.rand` with
    `numpy.random.default_rng()` in `test_embeddings.py`.
  - **S3776**: Reduced cognitive complexity in 5 functions by extracting
    helpers: `_evaluate_candidate` + `_hard_delete_expired` (retention),
    `_extract_session_signals` (handoffs), `_handle_log_event` +
    `_handle_session_end` (router), `_resolve_kind` + `_resolve_body` +
    `_extract_tool_input_parts` + `_extract_tool_response_parts` (sanitize).
  - **S7679**: Assigned positional parameters to local variables in
    `session-end.sh` `_jstr` function.
  - **S131**: Added default case `*) ;;` to `case` statement in
    `session-end.sh`.

### Added

- 61 regression tests covering all SonarQube fixes (Windows path stripping,
  kind resolution, error regex, retention sweep, handoff summaries, router
  pipeline, config constants, sanitize end-to-end).

## [0.15.3] - 2026-05-29

### Fixed

- **Black console window on Windows.** v0.15.2 spawned the server with
  `DETACHED_PROCESS`, which pops a visible console window for the console-subsystem
  Python. Switched to `CREATE_NO_WINDOW` (mutually exclusive with `DETACHED_PROCESS`),
  so the server runs hidden; survival across Claude Code's shutdown is still ensured by
  `CREATE_BREAKAWAY_FROM_JOB` plus having no inherited console to be signalled.

### Added

- `.gitattributes` forcing `*.sh` to LF. With `core.autocrlf=true` a Windows checkout
  rewrote the shell hooks to CRLF, and the stray `\r` was carried into resolved paths
  (it briefly broke the spool path during development). Hooks now stay LF everywhere.

## [0.15.2] - 2026-05-29

### Fixed

- **SessionEnd "Hook cancelled" on Windows (3 root causes).** "Hook cancelled" is not
  a timeout — Claude Code kills the hook's process tree at shutdown without waiting.
  Three compounding Windows bugs meant session-end events were silently lost:
  - **Server died with Claude Code.** `daemon.py` spawned the HTTP server with only
    `CREATE_NEW_PROCESS_GROUP`, which does not escape Claude Code's kill-on-close Job
    Object — so the "detached" server was killed the instant the editor closed. It now
    spawns with `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`,
    falling back without breakaway when the job forbids it.
  - **`is_server_running()` reported dead servers as alive.** `_pid_exists` used
    `OpenProcess`, whose handle is valid even for a terminated or recycled PID, so
    `ensure_server` never restarted a dead server. It now checks
    `GetExitCodeProcess == STILL_ACTIVE`, and `ensure_server` treats the `/health`
    endpoint as the liveness authority (immune to stale/recycled PIDs).
  - **The hook raced shutdown.** A foreground `curl` (~0.8s) was cancelled before
    completing; a backgrounded `curl` exits fast but the orphan dies before sending.
    The hook now performs no network at all.

### Added

- **Durable spool for lifecycle events.** The SessionEnd hook parses with native bash
  regex (zero subprocess; `read -r -d ''` instead of `cat`) and writes the event to
  `spool/<session>.json` in ~0.4s — fast enough to finish before any kill, and durable
  if it doesn't. The server drains `spool/*.json` on startup and every 3s via
  `handle_hook_event`, so capture is independent of the shutdown race and of the server
  being alive at session-end. The server advertises the spool dir in a runtime file
  (`~/.mymem0ry/runtime`) so the hook resolves the path without re-deriving it.
- `mymem0ry --help` now shows a one-line description for every command.

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

[Unreleased]: https://github.com/cccadet/myMem0ry/compare/v0.15.3...HEAD
[0.15.3]: https://github.com/cccadet/myMem0ry/compare/v0.15.2...v0.15.3
[0.15.2]: https://github.com/cccadet/myMem0ry/compare/v0.15.1...v0.15.2
[0.14.5]: https://github.com/cccadet/myMem0ry/compare/v0.14.4...v0.14.5
[0.14.4]: https://github.com/cccadet/myMem0ry/compare/v0.14.3...v0.14.4
[0.14.3]: https://github.com/cccadet/myMem0ry/compare/v0.14.2...v0.14.3
[0.14.2]: https://github.com/cccadet/myMem0ry/compare/v0.14.1...v0.14.2
[0.14.1]: https://github.com/cccadet/myMem0ry/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/cccadet/myMem0ry/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/cccadet/myMem0ry/releases/tag/v0.13.0
[0.12.2]: https://github.com/cccadet/myMem0ry/compare/v0.3.0...v0.12.2
[0.2.0]: https://github.com/cccadet/myMem0ry/releases/tag/v0.2.0
