"""Auto-daemon management for the myMem0ry HTTP server."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .config import MemoryConfig


def get_pid_file() -> Path:
    return Path(MemoryConfig().server_pid_file)


def get_server_url() -> str:
    cfg = MemoryConfig()
    return f"http://{cfg.server_host}:{cfg.server_port}"


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        # OpenProcess succeeds even for a terminated process whose kernel object
        # still lingers (or a recycled PID), so the handle alone is not proof of
        # life — GetExitCodeProcess must report STILL_ACTIVE.
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def is_server_running() -> bool:
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        if not _pid_exists(pid):
            raise ProcessLookupError(pid)
        return True
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return False


def _wait_for_health(url: str, timeout: float = 5.0) -> bool:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


def ensure_server() -> str:
    """Start the server if not running. Returns server URL.

    Blocks until health check passes or timeout.
    """
    url = get_server_url()
    # Health is the source of truth. A stale-but-alive PID file or a recycled PID
    # both make is_server_running() unreliable, so we ask the port directly: if it
    # answers, a server is up and we must NOT spawn a duplicate.
    if _wait_for_health(url, timeout=1.0):
        return url

    pid_file = get_pid_file()
    # Nothing is answering — clear any stale PID (terminate it if it somehow lingers)
    # so the liveness check can't keep reporting a dead server as alive.
    try:
        if pid_file.exists():
            old_pid = int(pid_file.read_text().strip())
            if _pid_exists(old_pid):
                _terminate_pid(old_pid)
    except (ValueError, OSError):
        pass
    pid_file.unlink(missing_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    cfg = MemoryConfig()
    cmd = [
        sys.executable,
        "-m",
        "mem0ry.mcp_server",
    ]
    env = {
        **os.environ,
        "MCP_TRANSPORT": "streamable-http",
        "MCP_HOST": cfg.server_host,
        "MCP_PORT": str(cfg.server_port),
    }

    proc = _spawn_detached(cmd, env)
    pid_file.write_text(str(proc.pid))

    _wait_for_health(url, timeout=8.0)
    return url


def _spawn_detached(cmd: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    """Launch the server fully detached so it outlives the caller.

    On Windows a hook-spawned child is added to Claude Code's Job Object, which is
    configured to kill its processes when the job closes — so the server died the
    moment Claude Code exited. DETACHED_PROCESS + CREATE_BREAKAWAY_FROM_JOB escapes
    that job; if the job forbids breakaway (raises OSError) we retry without it.
    """
    kwargs: dict[str, Any] = {
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
        return subprocess.Popen(cmd, **kwargs)

    # CREATE_NO_WINDOW runs the console-subsystem python with no visible window
    # (DETACHED_PROCESS would pop a black console window). It's mutually exclusive
    # with DETACHED_PROCESS, so we rely on CREATE_BREAKAWAY_FROM_JOB to escape Claude
    # Code's kill-on-close job and on having no inherited console to be signalled.
    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    base_flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    try:
        return subprocess.Popen(
            cmd, creationflags=base_flags | CREATE_BREAKAWAY_FROM_JOB, **kwargs
        )
    except OSError:
        # Job doesn't allow breakaway (ERROR_ACCESS_DENIED). No-window + own group is
        # the best we can do; the server may stay in the job but won't show a window.
        return subprocess.Popen(cmd, creationflags=base_flags, **kwargs)


def _terminate_pid(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_TERMINATE = 1
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            kernel32.TerminateProcess(handle, 1)
            kernel32.CloseHandle(handle)
    else:
        os.kill(pid, signal.SIGTERM)


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        _terminate_pid(pid)
    else:
        os.kill(pid, signal.SIGKILL)


def stop_server() -> bool:
    """Graceful stop via PID file. Returns True if stopped."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
        _terminate_pid(pid)
        time.sleep(0.3)
        if _pid_exists(pid):
            _kill_pid(pid)
        pid_file.unlink(missing_ok=True)
        return True
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return False


def server_status() -> dict[str, Any]:
    """Return server status info."""
    url = get_server_url()
    pid_file = get_pid_file()
    running = is_server_running()
    pid: int | None = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            pass

    import urllib.request

    health: dict[str, Any] | None = None
    if running:
        try:
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                import json

                health = json.loads(resp.read())
        except OSError:
            pass

    return {
        "running": running,
        "pid": pid,
        "url": url,
        "pid_file": str(pid_file),
        "health": health,
    }
