"""Git-based context resolution for memory scoping."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=2,
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
