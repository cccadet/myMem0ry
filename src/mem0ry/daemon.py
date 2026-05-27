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
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
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
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        pid_file.unlink(missing_ok=True)
        return False


def _wait_for_health(url: str, timeout: float = 5.0) -> bool:
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.1)
    return False


def ensure_server() -> str:
    """Start the server if not running. Returns server URL.

    Blocks until health check passes or timeout.
    """
    url = get_server_url()
    if is_server_running():
        return url

    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "mem0ry.mcp_server",
        "--transport",
        "streamable-http",
    ]

    popen_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **popen_kwargs,
    )

    pid_file.write_text(str(proc.pid))

    if not _wait_for_health(url, timeout=8.0):
        return url

    return url


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
    except (ValueError, ProcessLookupError, PermissionError, OSError):
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
    import urllib.error

    health: dict[str, Any] | None = None
    if running:
        try:
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                import json

                health = json.loads(resp.read())
        except (urllib.error.URLError, OSError):
            pass

    return {
        "running": running,
        "pid": pid,
        "url": url,
        "pid_file": str(pid_file),
        "health": health,
    }
