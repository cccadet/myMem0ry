"""Git-based auto-sync helpers for the myMem0ry data directory.

The data directory is synchronized through a regular git repository.
Auto-sync is opt-in and failures are logged, never fatal.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_COMMIT_MESSAGE = "auto: sync myMem0ry data"


class GitSyncError(Exception):
    """Raised when a git operation fails."""


def _git_cmd(repo_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo_dir`` and return the completed process."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitSyncError("git executable not found on PATH") from exc
    except OSError as exc:
        raise GitSyncError(f"failed to run git: {exc}") from exc

    if check and result.returncode != 0:
        raise GitSyncError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def is_git_repo(repo_dir: Path) -> bool:
    """Return True when ``repo_dir`` is inside a git repository."""
    try:
        result = _git_cmd(repo_dir, "rev-parse", "--is-inside-work-tree", check=False)
        return result.returncode == 0 and result.stdout.strip() == "true"
    except GitSyncError:
        return False


def git_status(repo_dir: Path) -> dict[str, Any]:
    """Return a summary of the git repository status."""
    if not is_git_repo(repo_dir):
        return {"enabled": False, "reason": "not a git repository"}

    try:
        branch = _git_cmd(repo_dir, "branch", "--show-current").stdout.strip()
        status = _git_cmd(repo_dir, "status", "--porcelain").stdout.strip()
        remote = _git_cmd(repo_dir, "remote", "get-url", "origin", check=False).stdout.strip()
    except GitSyncError as exc:
        return {"enabled": False, "reason": str(exc)}

    return {
        "enabled": True,
        "branch": branch,
        "remote": remote or None,
        "clean": status == "",
        "changes": status.splitlines() if status else [],
    }


def git_pull(repo_dir: Path, remote: str = "origin", branch: str = "main") -> str:
    """Pull the latest changes from ``remote/branch``.

    Uses ``--rebase`` so local commits are replayed on top of remote commits,
    keeping a linear history for single-user workflows.
    """
    _git_cmd(repo_dir, "pull", "--rebase", remote, branch)
    return f"pulled {remote}/{branch}"


def git_push(repo_dir: Path, remote: str = "origin", branch: str = "main") -> str:
    """Push the current branch to ``remote/branch``."""
    _git_cmd(repo_dir, "push", remote, branch)
    return f"pushed to {remote}/{branch}"


def git_commit_all(repo_dir: Path, message: str = DEFAULT_COMMIT_MESSAGE) -> str | None:
    """Stage all changes and commit if there is anything to commit.

    Returns the commit hash, or None when the working tree is clean.
    """
    status = _git_cmd(repo_dir, "status", "--porcelain").stdout.strip()
    if not status:
        return None

    _git_cmd(repo_dir, "add", "-A")
    result = _git_cmd(repo_dir, "commit", "-m", message)
    # Extract the generated commit hash from the first line of output.
    first_line = result.stdout.strip().splitlines()[0]
    if first_line.startswith("["):
        parts = first_line.split()
        if len(parts) >= 2:
            return parts[-1].rstrip("]")
    return "committed"


def _resolve_repo_dir(db_path: Path, override: str | None = None) -> Path:
    """Return the git repository directory for auto-sync."""
    if override:
        return Path(override).expanduser().resolve()
    return db_path.resolve().parent


def _load_config() -> dict[str, Any]:
    """Read git-sync settings from environment variables."""
    import os

    return {
        "enabled": os.environ.get("MEM0RY_GIT_AUTO_SYNC", "0") == "1",
        "remote": os.environ.get("MEM0RY_GIT_SYNC_REMOTE", "origin"),
        "branch": os.environ.get("MEM0RY_GIT_SYNC_BRANCH", "main"),
        "dir": os.environ.get("MEM0RY_GIT_SYNC_DIR", None),
    }


def auto_sync_before_read(db_path: Path) -> None:
    """Pull before reading when git auto-sync is enabled.

    Failures are logged so that a network or git problem does not break
    ``get_context`` for the agent.
    """
    cfg = _load_config()
    if not cfg["enabled"]:
        return

    repo_dir = _resolve_repo_dir(db_path, cfg["dir"])
    if not is_git_repo(repo_dir):
        logger.debug("git auto-sync skipped: %s is not a git repository", repo_dir)
        return

    try:
        git_pull(repo_dir, cfg["remote"], cfg["branch"])
        logger.debug("git auto-sync pulled before read in %s", repo_dir)
    except GitSyncError as exc:
        logger.warning("git auto-sync pull failed: %s", exc)


def auto_sync_after_write(db_path: Path, message: str = DEFAULT_COMMIT_MESSAGE) -> None:
    """Commit and push after writing when git auto-sync is enabled.

    Failures are logged so that a git problem does not break memory writes.
    """
    cfg = _load_config()
    if not cfg["enabled"]:
        return

    repo_dir = _resolve_repo_dir(db_path, cfg["dir"])
    if not is_git_repo(repo_dir):
        logger.debug("git auto-sync skipped: %s is not a git repository", repo_dir)
        return

    try:
        commit = git_commit_all(repo_dir, message)
        if commit:
            git_push(repo_dir, cfg["remote"], cfg["branch"])
            logger.debug("git auto-sync pushed after write: %s", commit)
        else:
            logger.debug("git auto-sync: nothing to commit in %s", repo_dir)
    except GitSyncError as exc:
        logger.warning("git auto-sync push failed: %s", exc)
