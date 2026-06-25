"""Tests for git-based auto-sync helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from mem0ry.db.git_sync import (
    GitSyncError,
    git_commit_all,
    git_pull,
    git_push,
    git_status,
    is_git_repo,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available on PATH"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--bare")
    return path


def _clone_repo(source: Path, dest: Path) -> Path:
    _git(dest.parent, "clone", str(source), str(dest.name))
    _git(dest, "config", "user.email", "test@example.com")
    _git(dest, "config", "user.name", "Test")
    _git(dest, "branch", "-M", "main")
    return dest


def test_is_git_repo_true(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    assert is_git_repo(repo) is True


def test_is_git_repo_false(tmp_path: Path) -> None:
    assert is_git_repo(tmp_path) is False


def test_git_status_reports_not_a_repo(tmp_path: Path) -> None:
    status = git_status(tmp_path)
    assert status["enabled"] is False
    assert "not a git repository" in status["reason"]


def test_git_commit_all_creates_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "memories.db").write_text("hello")
    commit = git_commit_all(repo, "initial")

    assert commit is not None
    log = _git(repo, "log", "--oneline").stdout
    assert "initial" in log


def test_git_commit_all_clean_returns_none(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "file.txt").write_text("x")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    assert git_commit_all(repo) is None


def test_git_pull_and_push(tmp_path: Path) -> None:
    bare = _init_repo(tmp_path / "bare.git")
    clone_a = _clone_repo(bare, tmp_path / "a")
    clone_b = _clone_repo(bare, tmp_path / "b")

    (clone_a / "memories.db").write_text("from-a")
    git_commit_all(clone_a, "add a")
    assert "pushed" in git_push(clone_a, "origin", "main")

    status_before = git_status(clone_b)
    assert status_before["clean"] is True

    git_pull(clone_b, "origin", "main")
    assert (clone_b / "memories.db").read_text() == "from-a"


def test_git_status_reports_clean_and_remote(tmp_path: Path) -> None:
    bare = _init_repo(tmp_path / "bare.git")
    clone = _clone_repo(bare, tmp_path / "clone")

    status = git_status(clone)
    assert status["enabled"] is True
    assert status["clean"] is True
    assert status["remote"] == str(bare)

    (clone / "new.txt").write_text("x")
    status = git_status(clone)
    assert status["clean"] is False
    assert len(status["changes"]) == 1


def test_git_pull_conflict_raises(tmp_path: Path) -> None:
    bare = _init_repo(tmp_path / "bare.git")
    clone_a = _clone_repo(bare, tmp_path / "a")
    clone_b = _clone_repo(bare, tmp_path / "b")

    (clone_a / "memories.db").write_text("a")
    git_commit_all(clone_a, "a")
    git_push(clone_a, "origin", "main")

    (clone_b / "memories.db").write_text("b")
    git_commit_all(clone_b, "b")

    with pytest.raises(GitSyncError):
        git_pull(clone_b, "origin", "main")
