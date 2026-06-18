"""Tests for hooks CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from mem0ry.cli.hooks import _detect_agent_dir, _hooks_dir, hooks


def test_hooks_path_prints_directory(capsys: pytest.CaptureFixture[str]) -> None:
    hooks(path=True)
    captured = capsys.readouterr()
    assert captured.out.strip().endswith("hooks")
    assert Path(captured.out.strip()).is_dir()


def test_hooks_config_prints_snippet(capsys: pytest.CaptureFixture[str]) -> None:
    hooks(path=False, install=False, config=True)
    captured = capsys.readouterr()
    assert "settings.json" in captured.out
    assert "SessionStart" in captured.out
    assert "SessionEnd" in captured.out


def test_hooks_no_args_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    hooks(path=False, install=False, config=False)
    captured = capsys.readouterr()
    assert "Usage:" in captured.out


def test_hooks_dir_locates_existing_directory() -> None:
    hooks_dir = _hooks_dir()
    assert hooks_dir.is_dir()
    assert (hooks_dir / "claude-code").is_dir()


def test_detect_agent_dir_returns_none_when_nothing_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _detect_agent_dir() is None


def test_detect_agent_dir_finds_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _detect_agent_dir() == claude_dir


def test_hooks_install_no_agent_detected(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with pytest.raises(typer.Exit):
        hooks(path=False, install=True, config=False)
    captured = capsys.readouterr()
    assert "Could not detect agent" in captured.err
