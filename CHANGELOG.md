# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

[Unreleased]: https://github.com/cccadet/myMem0ry/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/cccadet/myMem0ry/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/cccadet/myMem0ry/releases/tag/v0.2.0
