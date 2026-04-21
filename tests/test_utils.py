"""Tests for utils.paths and utils.logging."""

from __future__ import annotations

import logging
from pathlib import Path

from mem0ry.utils.logging import configure_logging
from mem0ry.utils.paths import ensure_dir


def test_ensure_dir_creates(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c"
    result = ensure_dir(target)
    assert result.is_dir()


def test_ensure_dir_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    result = ensure_dir(target)
    assert result.is_dir()


def test_configure_logging_returns_logger() -> None:
    logger = configure_logging()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "mem0ry"


def test_configure_logging_json_output(capfd) -> None:
    import json

    logger = configure_logging()
    logger.handlers.clear()
    logger = configure_logging()
    logger.info("test_structured_log")
    logger.handlers.clear()
    captured = capfd.readouterr()
    lines = [l for l in captured.err.strip().split("\n") if l.strip()]
    assert lines, "Expected JSON log output on stderr"
    data = json.loads(lines[-1])
    assert data["msg"] == "test_structured_log"
    assert data["level"] == "INFO"
    assert "ts" in data
