# MCP & Web Integration

## MCP tools reference

`src/mem0ry/mcp_server.py` exposes the following FastMCP tools. Agents call these over stdio or HTTP.

### `save_memory(title, content, scope="global", memory_type="log", cwd="", ...)`

Creates a curated memory. `cwd` is used to auto-resolve `project_id`, `project_path`, `context`, and `session_id`. The memory is also written as a `.md` file in `MEMORIES_DIR`.

Critical instruction in the tool docstring: **must call `save_memory` after every significant decision or fact.**

### `get_context(cwd="", top_k=5)`

Returns aggregated memories across scopes in priority order (session → context → project → global). Automatically calls `auto_sync_before_read` when git auto-sync is enabled.

If `compress_enabled` is set in `MemoryConfig`, results are passed through `compress_memory_array` (optional SmartCrusher integration).

### `search_memory(query, cwd="", scope=None, memory_type=None, tags=None, top_k=5)`

Searches curated memories. Supports:
- Scope filtering
- Memory type filtering
- Tag filtering
- Query expansion via spaCy (if the expander is loaded)

Returns previews with `id`, `title`, `scope`, `memory_type`, `preview`, `created_at`, `pinned`.

### `search_conversations(query, top_k=5, backend="ripgrep")`

Searches archived conversation `.md` files (not the curated memory store). Backend is selectable per call. Returns path-based previews.

### `read_memory(path)`

Reads a single memory or conversation transcript by relative path. Includes path-traversal guards.

### `memory_pin(memory_id)` / `memory_unpin(memory_id)`

Pins or unpins a memory. Pinned memories are exempt from retention decay.

### `begin_handoff(summary, open_questions, next_steps, cwd="")`

Creates a handoff record with status `open`.

### `accept_handoff(handoff_id, cwd="")`

Marks a handoff as accepted and returns the full summary.

### `close_handoff(handoff_id)`

Closes a handoff without accepting it.

### `end_session(session_id, summary=None)`

Updates all session memories and optionally writes a session summary.

## Web UI routes

The read-only web UI is served by a Starlette app mounted on the MCP HTTP server. Routes are defined in `src/mem0ry/web/__init__.py`.

| Route | Handler | Purpose |
|---|---|---|
| `GET /` | `dashboard` | Stats, recent memories, handoffs |
| `GET /projects` | `projects_page` | Project list with counts |
| `GET /project/{id}` | `project_detail` | Project memories + metadata |
| `GET /project/{id}/observations` | `project_observations` | Observations for a project |
| `GET /memory/{id}` | `memory_detail` | Memory detail |
| `GET /memory/{id}/edit` | `memory_edit_form` | Edit form |
| `POST /memory/{id}/edit` | `memory_edit_save` | Save edits |
| `POST /memory/{id}/pin` | `pin_memory_page` | Pin memory |
| `POST /memory/{id}/unpin` | `unpin_memory_page` | Unpin memory |
| `POST /memory/{id}/restore` | `restore_memory_page` | Restore from trash |
| `POST /memory/{id}/delete` | `delete_memory_page` | Soft delete |
| `GET /search` | `search_page` | Full-text search UI |
| `GET /handoffs` | `handoffs_page` | Open handoffs list |
| `GET /handoff/{id}` | `handoff_detail` | Handoff detail |
| `POST /handoff/{id}/close` | `close_handoff_page` | Close handoff |
| `POST /handoff/{id}/delete` | `delete_handoff_page` | Delete handoff |
| `GET /export` | `export_page` | Export UI |
| `POST /export/json` | `export_memories_page` | JSON export |
| `GET /import` | `import_page` | Import UI |
| `POST /import/json` | `import_memories_page` | JSON import |
| `GET /trash` | `trash_page` | Deleted memories |
| `POST /trash/batch-delete` | `batch_delete_memories` | Permanent delete |
| `GET /audit` | `audit_page` | Audit log |

Templates are plain Python functions in `src/mem0ry/web/templates.py` (no Jinja dependency). i18n helpers are in `web/i18n.py`.

## Authentication and CORS

`src/mem0ry/auth.py` provides:

- **`AuthMiddleware`** — checks `Authorization: Bearer <token>` against `MEM0RY_TOKEN`. Skips auth if no token is configured.
- **`CORSMiddleware`** — simple CORS headers for cross-origin browser access.
- **`check_host`** — validates `Host` header against `MEM0RY_ALLOWED_HOSTS`.

Both middlewares are mounted on the HTTP server in `mcp_server.py`.

## Daemon and auto-start

`src/mem0ry/daemon.py` manages the background HTTP process:

- `is_server_running()` — checks PID file and process liveness (cross-platform).
- `start_server(...)` — spawns `python -m mem0ry.mcp_server` with `MCP_TRANSPORT=streamable-http`.

The MCP server calls `start_server()` on initialization when HTTP transport is active, so the web UI is available without manual `mymem0ry serve`.
