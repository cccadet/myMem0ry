"""Git-based context resolution for memory scoping."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

# On Windows, suppress the console window when spawning git. Without this,
# spawning a subprocess from inside the MCP stdio server (whose own stdio are
# pipes) can deadlock, because the child inherits the server's pipe handles.
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _git(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=_CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def resolve_project_id(cwd: Path) -> str | None:
    """Return git remote URL (raw) as project identifier.

    Falls back to None if cwd is not inside a git repo.
    """
    return _git(cwd, "remote", "get-url", "origin")


def resolve_project_path(cwd: Path) -> str:
    """Return the absolute path of the current working directory."""
    return str(cwd.resolve())


def resolve_context(cwd: Path) -> str | None:
    """Return current git branch name as context identifier.

    Falls back to None if not in a git repo.
    """
    return _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")


def resolve_full_context(cwd: Path, session_id: str | None = None) -> dict[str, Any]:
    """Resolve all context dimensions from a working directory.

    Returns a dict with project_id, project_path, context, session_id.
    """
    return {
        "project_id": resolve_project_id(cwd),
        "project_path": resolve_project_path(cwd),
        "context": resolve_context(cwd),
        "session_id": session_id,
    }
