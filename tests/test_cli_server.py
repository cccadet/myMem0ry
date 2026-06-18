"""Tests for server CLI command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mem0ry.cli.server import observe, serve


def test_serve_foreground_sets_env_and_runs_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEM0RY_HOST", "127.0.0.1")
    monkeypatch.setenv("MEM0RY_PORT", "49374")

    with patch("mem0ry.mcp_server.main") as mock_main:
        serve(host="127.0.0.1", port=49374, detach=False)

    mock_main.assert_called_once()
    assert os.environ.get("MEM0RY_HOST") == "127.0.0.1"
    assert os.environ.get("MCP_HOST") == "127.0.0.1"


def test_serve_detach_spawns_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from mem0ry import config as config_module

    monkeypatch.setenv("MEM0RY_PID_FILE", str(tmp_path / "server.pid"))
    importlib.reload(config_module)

    mock_proc = MagicMock()
    mock_proc.pid = 4242

    with (
        patch("mem0ry.daemon.is_server_running", return_value=False),
        patch("subprocess.Popen", return_value=mock_proc) as popen_mock,
    ):
        serve(host="127.0.0.1", port=55555, detach=True)

    popen_mock.assert_called_once()
    env = popen_mock.call_args.kwargs["env"]
    assert env["MEM0RY_HOST"] == "127.0.0.1"
    assert env["MEM0RY_PORT"] == "55555"


def test_serve_detach_skips_when_already_running(capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEM0RY_PID_FILE", str(tmp_path / "server.pid"))

    with patch("mem0ry.daemon.is_server_running", return_value=True):
        serve(host="127.0.0.1", port=55555, detach=True)

    captured = capsys.readouterr()
    assert "already running" in captured.out


def test_observe_posts_event(capsys: pytest.CaptureFixture[str]) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"id": "obs-1"}'
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with (
        patch("mem0ry.daemon.ensure_server") as ensure_mock,
        patch("mem0ry.daemon.get_server_url", return_value="http://127.0.0.1:49374"),
        patch("urllib.request.urlopen", return_value=mock_response) as urlopen_mock,
    ):
        observe("log", "hello world", cwd="/tmp", session="sess-1", agent="opencode")

    ensure_mock.assert_called_once()
    urlopen_mock.assert_called_once()
    captured = capsys.readouterr()
    assert "obs-1" in captured.out


def test_observe_server_not_reachable(capsys: pytest.CaptureFixture[str]) -> None:
    import urllib.error

    with (
        patch("mem0ry.daemon.ensure_server"),
        patch("mem0ry.daemon.get_server_url", return_value="http://127.0.0.1:49374"),
        patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
    ):
        observe(kind="log", content="hello", session="sess-1", cwd="/tmp", agent="manual")

    captured = capsys.readouterr()
    assert "Server not reachable" in captured.err
