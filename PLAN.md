# myMem0ry — Unified Architecture & Implementation Plan

A Python package managed with **uv** to import conversation histories from ChatGPT, Gemini, and Claude into a **mem0** instance (local-first, cloud-compatible).

---

## 1. Goals

- Unified ingestion layer for multiple LLM providers (ChatGPT, Gemini, Claude)
- Normalize all conversation formats into a single canonical schema
- Store in **mem0** — local-first with cloud-compatible option
- Incremental sync with deduplication (idempotent imports)
- Extensible design — easy to add new providers in the future
- Clean CLI powered by **Typer**

---

## 2. Architecture Overview

The package follows a **Ports & Adapters (Hexagonal)** design with an **ETL pipeline** at its core:

```
                    ┌──────────────────────┐
                    │      CLI Layer       │
                    │  (Typer commands)    │
                    └─────────┬────────────┘
                              │
                    ┌─────────▼────────────┐
                    │     Orchestrator     │
                    │   (Import Manager)   │
                    └─────────┬────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
  ┌────▼────┐          ┌──────▼─────┐         ┌──────▼─────┐
  │ ChatGPT │          │   Gemini   │         │   Claude   │
  │ Adapter │          │  Adapter   │         │  Adapter   │
  └────┬────┘          └──────┬─────┘         └──────┬─────┘
       │                      │                      │
       └──────────────┬────────┴──────────────┬───────┘
                      │                       │
              ┌───────▼────────┐    ┌──────────▼────────┐
              │  Normalization │    │   State Store     │
              │   (Schema)     │    │  (Sync / Dedupe)  │
              └───────┬────────┘    └──────────┬────────┘
                      │                        │
                      └────────────┬───────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │         mem0 Sink           │
                    │  LocalSink  |  CloudSink    │
                    └─────────────────────────────┘
```

### Pipeline stages

Each import runs through the following deterministic steps:

1. **Discover** — locate and validate export files on disk
2. **Parse** — extract raw data using the provider-specific adapter
3. **Normalize** — map to canonical `Conversation` / `Message` schema
4. **Chunk** — split long conversations into meaningful memory units
5. **Deduplicate** — skip records already present using content hash + source ID
6. **Enrich** — attach provenance metadata (source, timestamps, user_id)
7. **Write** — push to mem0 via the active sink
8. **Report** — emit JSON import summary

---

## 3. Canonical Data Model

All adapters output to this unified schema (defined with **Pydantic**):

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Message:
    source_message_id: str | None
    role: str                   # "user" | "assistant" | "system" | "tool"
    content: str
    created_at: datetime | None
    metadata: dict              # provider-specific extras

@dataclass
class Conversation:
    id: str                     # deterministic: hash(source + source_id)
    source: str                 # "chatgpt" | "gemini" | "claude"
    source_conversation_id: str
    title: str | None
    participants: list[str]
    messages: list[Message]
    created_at: datetime | None
    updated_at: datetime | None
    metadata: dict              # provenance: source_provider, imported_at, tags, hash
```

Provenance fields stored in `metadata` for every mem0 write:

| Field | Purpose |
|---|---|
| `source_provider` | Traceability |
| `source_conversation_id` | Re-import safety |
| `source_message_id` | Fine-grained deduplication |
| `imported_at` | Audit trail |
| `hash` | Idempotency key |
| `user_id` | mem0 user context |
| `tags` | Filtering / search |

---

## 4. Provider Adapters

Each adapter extends `BaseAdapter` and handles only its own export quirks:

```python
class BaseAdapter(ABC):
    @abstractmethod
    def parse(self, path: Path) -> list[Conversation]:
        pass
```

| Provider | Export Format | Notes |
|---|---|---|
| **ChatGPT** | `conversations.json` | Tree of mapping nodes — needs flattening |
| **Claude** | ZIP with per-conversation JSON files | Straightforward structure |
| **Gemini** | Google Takeout (JSON or HTML) | Multiple acquisition modes; treat as best-effort |

> **Note on Gemini:** Google's export is inconsistent across consumer and Workspace accounts. The adapter should support `account_export`, `html_export`, and `raw_json` source modes independently — avoid coupling to a single parser.

---

## 5. mem0 Sink Interface

The orchestrator never speaks to mem0 directly. Both sinks expose the same interface:

```python
class BaseSink(ABC):
    @abstractmethod
    def store(self, conv: Conversation, user_id: str) -> None:
        pass

class Mem0LocalSink(BaseSink):
    # Uses Memory() or Memory.from_config(...)
    # Local vector DB: Qdrant via Docker, or Chroma/FAISS for zero-infra
    # Optional: Ollama for local embeddings

class Mem0CloudSink(BaseSink):
    # Uses MemoryClient(api_key=MEM0_API_KEY)
    # Stateless — suitable for scheduled jobs and multi-user ingestion
```

**Ingestion strategy:** store one memory per conversation by default (recommended). Per-message ingestion is available via `--mode message` flag but is slower and more expensive with cloud mem0.

---

## 6. Deduplication Strategy

Use content hashing to make imports idempotent:

```python
hash = sha256(f"{source}:{source_conversation_id}:{messages_content}").hexdigest()
```

Store the hash in mem0 metadata. Before writing, check for an existing record with the same hash. This prevents duplicates even when running the importer multiple times on the same export file.

---

## 7. State Management (Incremental Sync)

A lightweight state store tracks the last sync cursor per provider:

```json
{
  "chatgpt": "2024-01-15T10:30:00Z",
  "gemini":  "2024-01-14T08:00:00Z",
  "claude":  "2024-01-16T12:00:00Z"
}
```

Storage options (ascending complexity):

- **JSON file** — simple, good for v1
- **SQLite** — better for concurrent/scheduled runs
- **Redis** — cloud-ready, for multi-user deployments

---

## 8. Configuration

Via **Pydantic BaseSettings**, loaded from environment variables or a `.env` file:

```env
# Backend selection
MEM0_BACKEND=local          # "local" or "cloud"

# Cloud backend
MEM0_API_KEY=mem0-xxxx

# Local backend
QDRANT_URL=localhost:6333
OPENAI_API_KEY=sk-xxxx      # if using OpenAI embeddings locally

# Optional
DEFAULT_USER_ID=me
STATE_STORE=state.json
```

---

## 9. CLI Interface

Built with **Typer**, with subcommands per provider plus a bulk import:

```bash
# Import from a specific provider
uv run mymemory chatgpt ./conversations.json --user-id me
uv run mymemory gemini  ./takeout/            --user-id me
uv run mymemory claude  ./claude_export.zip   --user-id me

# Import all providers from a directory
uv run mymemory all     ./exports/            --user-id me

# Utilities
uv run mymemory inspect  <path>               # preview what will be imported
uv run mymemory validate <path> --provider chatgpt
uv run mymemory status                        # show sync state
```

Flags available on all import commands:

| Flag | Description |
|---|---|
| `--dry-run` | Parse and validate without writing to mem0 |
| `--limit N` | Import only the N most recent conversations |
| `--since YYYY-MM-DD` | Only import conversations after this date |
| `--mode message\|conversation` | Granularity of mem0 writes |
| `--target local\|cloud` | Override the configured sink |

---

## 10. Project Structure

```
myMem0ry/
├── pyproject.toml
├── uv.lock
├── .env.example
├── README.md
│
└── src/
    └── mymemory/
        ├── __init__.py
        ├── cli.py                  # Typer entrypoint
        ├── config.py               # Pydantic BaseSettings
        ├── orchestrator.py         # Pipeline coordinator
        │
        ├── domain/
        │   ├── models.py           # Conversation, Message, ImportJob, ImportResult
        │   ├── enums.py            # SourceProvider, IngestionMode, etc.
        │   └── errors.py           # Custom exceptions
        │
        ├── providers/
        │   ├── base.py             # BaseAdapter ABC
        │   ├── chatgpt/
        │   │   ├── adapter.py
        │   │   ├── parser.py
        │   │   └── schema.py       # Raw ChatGPT-specific types
        │   ├── gemini/
        │   │   ├── adapter.py
        │   │   ├── parser.py
        │   │   └── schema.py
        │   └── claude/
        │       ├── adapter.py
        │       ├── parser.py
        │       └── schema.py
        │
        ├── sinks/
        │   ├── base.py             # BaseSink ABC
        │   ├── mem0_local.py       # Memory() wrapper
        │   └── mem0_cloud.py       # MemoryClient() wrapper
        │
        ├── application/
        │   ├── normalize.py        # Raw → Conversation mapper
        │   ├── dedupe.py           # Hash-based deduplication
        │   ├── chunking.py         # Conversation splitter
        │   └── reporting.py        # Import result emitter
        │
        └── infrastructure/
            ├── state_store.py      # Sync cursor persistence
            ├── hashing.py          # SHA-256 helpers
            └── logging.py          # Structured logging setup

tests/
├── fixtures/                       # Anonymized sample export files
│   ├── chatgpt_sample.json
│   ├── gemini_sample.json
│   └── claude_sample.zip
├── test_parsers.py                 # Parametrized across all providers
├── test_normalizer.py
├── test_dedupe.py
├── test_orchestrator.py
└── test_cli.py
```

---

## 11. pyproject.toml

```toml
[project]
name = "mymemory"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
  "mem0ai",
  "pydantic>=2.0",
  "pydantic-settings",
  "typer",
  "rich",
  "python-dotenv",
  "httpx",
]

[project.scripts]
mymemory = "mymemory.cli:app"

[tool.uv]
dev-dependencies = [
  "pytest",
  "pytest-cov",
  "ruff",
  "mypy",
]
```

---

## 12. Open Questions (Decide Before Coding)

1. **Ingestion granularity** — one memory per conversation (faster, cheaper) or one per message (more granular)? Recommended default: per conversation.
2. **Local vector DB** — default to SQLite + Chroma (zero-infra) or require Qdrant via Docker?
3. **Gemini support priority** — full parser or "best-effort" for v1 given format inconsistencies?
4. **Privacy / anonymization** — any PII filtering needed before sending data to cloud mem0?
5. **Python version** — 3.11 minimum (broad compatibility) or 3.13 (latest)?

---

## 13. Execution Steps

Follow these phases in order. Each phase produces something runnable before moving on.

### Phase 1 — Project scaffold

```bash
uv init myMem0ry
cd myMem0ry
uv add mem0ai pydantic pydantic-settings typer rich python-dotenv httpx
uv add --dev pytest pytest-cov ruff mypy
```

- Create `src/mymemory/` package layout
- Add CLI entry point in `pyproject.toml`
- Add `.env.example` with all configuration keys
- Commit: *"chore: project scaffold"*

### Phase 2 — Domain models

- Create `domain/models.py` with `Message` and `Conversation` dataclasses
- Create `domain/enums.py` (SourceProvider, IngestionMode, SinkTarget)
- Create `domain/errors.py` (ParseError, DuplicateError, SinkError)
- Write unit tests with synthetic data to validate the schema
- Commit: *"feat: canonical domain models"*

### Phase 3 — mem0 sink interface

- Define `sinks/base.py` (`BaseSink` ABC)
- Implement `sinks/mem0_local.py` using `Memory()` or `Memory.from_config()`
- Implement `sinks/mem0_cloud.py` using `MemoryClient()`
- Create `config.py` with `Pydantic BaseSettings` to select the active sink
- Verify both sinks work manually against a local mem0 instance
- Commit: *"feat: mem0 sink layer (local + cloud)"*

### Phase 4 — ChatGPT adapter (MVP provider)

- Implement `providers/chatgpt/parser.py` — flatten the node-mapping tree in `conversations.json`
- Implement `providers/chatgpt/adapter.py` — filter empty/system messages, resolve timestamps
- Add `application/normalize.py` — map ChatGPT raw output to canonical `Conversation`
- Add test fixture `tests/fixtures/chatgpt_sample.json` (anonymized)
- Write `tests/test_parsers.py` covering happy path and edge cases
- Commit: *"feat: ChatGPT adapter + normalizer"*

### Phase 5 — Deduplication & state store

- Implement `infrastructure/hashing.py`
- Implement `application/dedupe.py` — check hash against mem0 metadata before writing
- Implement `infrastructure/state_store.py` — JSON file cursor for incremental sync
- Commit: *"feat: deduplication and state management"*

### Phase 6 — Orchestrator & CLI (first end-to-end run)

- Implement `orchestrator.py` — wire parse → normalize → chunk → dedupe → write → report
- Implement `cli.py` with `chatgpt` and `all` subcommands, `--dry-run` and `--limit` flags
- Run a full import of a sample `conversations.json` into local mem0 and verify retrieval
- Commit: *"feat: orchestrator and CLI — first e2e import working"*

### Phase 7 — Claude adapter

- Implement `providers/claude/` — parse ZIP export (one JSON per conversation)
- Add test fixture and parser tests
- Add `mymemory claude` CLI command
- Commit: *"feat: Claude adapter"*

### Phase 8 — Gemini adapter (best-effort)

- Implement `providers/gemini/` with multiple source modes: `account_export`, `html_export`, `raw_json`
- Document limitations clearly in README
- Add `mymemory gemini` CLI command
- Commit: *"feat: Gemini adapter (multi-mode)"*

### Phase 9 — Polish & hardening

- Add `--since`, `--mode`, `--target` flags to all import commands
- Implement `mymemory inspect` and `mymemory status` commands
- Add `application/reporting.py` — JSON import summary (parsed, skipped, failed, written)
- Add structured logging via `infrastructure/logging.py`
- Expand test coverage with parametrized tests across all three adapters
- Add integration test against a local mem0 instance (using a test user ID)
- Commit: *"feat: polish, reporting, and full test coverage"*

### Phase 10 — Documentation & release

- Write `README.md` with quickstart, configuration reference, and CLI usage
- Write `ARCHITECTURE.md` summarizing the design decisions
- Tag `v0.1.0`
- Publish to PyPI (optional): `uv build && uv publish`