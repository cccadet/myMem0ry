"""Tests for daemon management helpers."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _fresh_daemon(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    """Return a freshly imported daemon module that picks up the given env vars."""
    import importlib

    # Ensure config is reloaded first so MemoryConfig picks up env changes.
    from mem0ry import config as config_module

    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(config_module)

    from mem0ry import daemon as daemon_module

    return importlib.reload(daemon_module)


def test_get_server_url_uses_config(monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_HOST="127.0.0.1",
        MEM0RY_PORT="12345",
        MEM0RY_PID_FILE="/tmp/test-daemon.pid",
    )
    assert daemon.get_server_url() == "http://127.0.0.1:12345"


def test_pid_exists_negative_returns_false() -> None:
    from mem0ry.daemon import _pid_exists

    assert _pid_exists(-1) is False
    assert _pid_exists(0) is False


def test_pid_exists_current_process_true() -> None:
    from mem0ry.daemon import _pid_exists

    assert _pid_exists(os.getpid()) is True


def test_pid_exists_dead_process_false() -> None:
    from mem0ry.daemon import _pid_exists

    assert _pid_exists(99999999) is False


def test_is_server_running_no_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(tmp_path / "server.pid"),
    )
    assert daemon.is_server_running() is False


def test_is_server_running_stale_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("99999999")
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(pid_file),
    )
    assert daemon.is_server_running() is False
    assert not pid_file.exists()


def test_is_server_running_malformed_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("not-a-pid")
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(pid_file),
    )
    assert daemon.is_server_running() is False
    assert not pid_file.exists()


def test_wait_for_health_success() -> None:
    from mem0ry.daemon import _wait_for_health

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        assert _wait_for_health("http://127.0.0.1:49374", timeout=1.0) is True


def test_wait_for_health_timeout() -> None:
    from mem0ry.daemon import _wait_for_health

    with patch("urllib.request.urlopen", side_effect=OSError("no server")):
        assert _wait_for_health("http://127.0.0.1:49374", timeout=0.2) is False


def test_ensure_server_already_healthy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(tmp_path / "server.pid"),
    )

    with patch.object(daemon, "_wait_for_health", return_value=True):
        url = daemon.ensure_server()
    assert url == daemon.get_server_url()


def test_ensure_server_spawns_and_waits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(tmp_path / "server.pid"),
    )

    mock_proc = MagicMock()
    mock_proc.pid = 12345

    with (
        patch.object(daemon, "_wait_for_health", side_effect=[False, True]) as wait_mock,
        patch.object(daemon, "_spawn_detached", return_value=mock_proc) as spawn_mock,
    ):
        url = daemon.ensure_server()

    assert url == daemon.get_server_url()
    assert wait_mock.call_count == 2
    spawn_mock.assert_called_once()
    pid_file = Path(daemon.get_pid_file())
    assert pid_file.read_text() == "12345"
    pid_file.unlink(missing_ok=True)


def test_stop_server_no_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(tmp_path / "server.pid"),
    )
    assert daemon.stop_server() is False


def test_stop_server_terminates_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("12345")
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(pid_file),
    )

    with (
        patch.object(daemon, "_pid_exists", return_value=False) as exists_mock,
        patch.object(daemon, "_terminate_pid") as terminate_mock,
    ):
        assert daemon.stop_server() is True
        terminate_mock.assert_called_once_with(12345)
        exists_mock.assert_called_once_with(12345)

    assert not pid_file.exists()


def test_server_status_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _fresh_daemon(
        monkeypatch,
        MEM0RY_PID_FILE=str(tmp_path / "server.pid"),
    )

    with patch.object(daemon, "is_server_running", return_value=False):
        status = daemon.server_status()

    assert status["running"] is False
    assert status["url"] == daemon.get_server_url()
    assert "pid_file" in status


def test_terminate_pid_unix_uses_sigterm() -> None:
    from mem0ry.daemon import _terminate_pid

    with patch("os.kill") as mock_kill:
        _terminate_pid(12345)
        if sys.platform != "win32":
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)


def test_spawn_detached_unix_sets_new_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    cmd = [sys.executable, "-m", "mem0ry.mcp_server"]
    env = {"MCP_TRANSPORT": "streamable-http"}

    with patch("subprocess.Popen", return_value=mock_proc) as popen_mock:
        result = daemon_mod._spawn_detached(cmd, env)

    assert result == mock_proc
    popen_mock.assert_called_once()
    kwargs = popen_mock.call_args.kwargs
    assert kwargs["env"] == env
    assert kwargs["start_new_session"] is True


def test_server_status_with_health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"ok": true}'
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with (
        patch.object(daemon_mod, "is_server_running", return_value=True),
        patch("urllib.request.urlopen", return_value=mock_response),
    ):
        status = daemon_mod.server_status()

    assert status["running"] is True
    assert status["health"] == {"ok": True}


def test_stop_server_kills_then_hard_kills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("12345")
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(pid_file))

    with (
        patch.object(daemon_mod, "_pid_exists", return_value=True) as exists_mock,
        patch.object(daemon_mod, "_terminate_pid") as terminate_mock,
        patch.object(daemon_mod, "_kill_pid") as kill_mock,
        patch("mem0ry.daemon.time.sleep"),
    ):
        assert daemon_mod.stop_server() is True
        assert terminate_mock.call_count == 1
        assert kill_mock.call_count == 1
        assert exists_mock.call_count == 1

    assert not pid_file.exists()


def test_ensure_server_terminates_old_stale_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("12345")

    mock_proc = MagicMock()
    mock_proc.pid = 54321

    with (
        patch.object(daemon_mod, "_wait_for_health", side_effect=[False, True]),
        patch.object(daemon_mod, "_pid_exists", return_value=True),
        patch.object(daemon_mod, "_terminate_pid") as terminate_mock,
        patch.object(daemon_mod, "_spawn_detached", return_value=mock_proc),
    ):
        daemon_mod.ensure_server()

    terminate_mock.assert_called_once_with(12345)
    assert pid_file.read_text() == "54321"


def test_server_status_health_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))

    with (
        patch.object(daemon_mod, "is_server_running", return_value=True),
        patch("urllib.request.urlopen", side_effect=OSError("boom")),
    ):
        status = daemon_mod.server_status()

    assert status["running"] is True
    assert status["health"] is None


def test_pid_exists_windows_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    fake_kernel = MagicMock()
    fake_kernel.OpenProcess.return_value = 1
    fake_exit_code = MagicMock()
    fake_exit_code.value = 259  # STILL_ACTIVE
    fake_kernel.GetExitCodeProcess.return_value = True
    fake_wintypes = MagicMock()
    fake_wintypes.DWORD.return_value = fake_exit_code

    fake_ctypes = MagicMock()
    fake_ctypes.wintypes = fake_wintypes
    fake_ctypes.byref.return_value = None
    fake_ctypes.windll.kernel32 = fake_kernel

    modules = {"ctypes": fake_ctypes, "ctypes.wintypes": fake_wintypes}
    with patch.dict("sys.modules", modules):
        from mem0ry.daemon import _pid_exists

        assert _pid_exists(1234) is True
        fake_kernel.CloseHandle.assert_called_once_with(1)


def test_ensure_server_propagates_spawn_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))

    with (
        patch.object(daemon_mod, "_wait_for_health", return_value=False),
        patch.object(daemon_mod, "_spawn_detached", side_effect=RuntimeError("spawn failed")),
    ):
        with pytest.raises(RuntimeError, match="spawn failed"):
            daemon_mod.ensure_server()


def test_stop_server_invalid_pid_file_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("not-a-pid")
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(pid_file))
    assert daemon_mod.stop_server() is False
    assert not pid_file.exists()


def test_ensure_server_skips_terminate_when_old_pid_dead(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("12345")

    mock_proc = MagicMock()
    mock_proc.pid = 54321

    with (
        patch.object(daemon_mod, "_wait_for_health", side_effect=[False, True]),
        patch.object(daemon_mod, "_pid_exists", return_value=False),
        patch.object(daemon_mod, "_terminate_pid") as terminate_mock,
        patch.object(daemon_mod, "_spawn_detached", return_value=mock_proc),
    ):
        daemon_mod.ensure_server()

    terminate_mock.assert_not_called()
    assert pid_file.read_text() == "54321"


def test_ensure_server_ignores_invalid_old_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(tmp_path / "server.pid"))
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("not-a-pid")

    mock_proc = MagicMock()
    mock_proc.pid = 54321

    with (
        patch.object(daemon_mod, "_wait_for_health", side_effect=[False, True]),
        patch.object(daemon_mod, "_spawn_detached", return_value=mock_proc),
    ):
        daemon_mod.ensure_server()

    assert pid_file.read_text() == "54321"


def test_server_status_invalid_pid_file_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = tmp_path / "server.pid"
    pid_file.write_text("not-a-pid")
    daemon_mod = _fresh_daemon(monkeypatch, MEM0RY_PID_FILE=str(pid_file))

    with patch.object(daemon_mod, "is_server_running", return_value=True):
        status = daemon_mod.server_status()

    assert status["pid"] is None


def test_kill_pid_unix_uses_sigkill() -> None:
    from mem0ry.daemon import _kill_pid

    with patch("os.kill") as mock_kill:
        _kill_pid(12345)
        if sys.platform != "win32":
            mock_kill.assert_called_once_with(12345, signal.SIGKILL)



