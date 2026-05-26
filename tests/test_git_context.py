"""Tests for utils.git_context — git-based context resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path

from mem0ry.utils.git_context import (
    resolve_context,
    resolve_full_context,
    resolve_project_id,
    resolve_project_path,
)


def test_resolve_project_id_in_git_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "github.com/user/repo"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    assert resolve_project_id(tmp_path) == "github.com/user/repo"


def test_resolve_project_id_no_git(tmp_path: Path) -> None:
    assert resolve_project_id(tmp_path) is None


def test_resolve_project_path(tmp_path: Path) -> None:
    result = resolve_project_path(tmp_path)
    assert result == str(tmp_path.resolve())


def test_resolve_context_in_git_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", "feat/auth"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    assert resolve_context(tmp_path) == "feat/auth"


def test_resolve_context_no_git(tmp_path: Path) -> None:
    assert resolve_context(tmp_path) is None


def test_resolve_full_context(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "github.com/user/repo"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", "main"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )

    ctx = resolve_full_context(tmp_path, session_id="s1")
    assert ctx["project_id"] == "github.com/user/repo"
    assert ctx["project_path"] == str(tmp_path.resolve())
    assert ctx["context"] == "main"
    assert ctx["session_id"] == "s1"


def test_resolve_full_context_no_git(tmp_path: Path) -> None:
    ctx = resolve_full_context(tmp_path)
    assert ctx["project_id"] is None
    assert ctx["project_path"] == str(tmp_path.resolve())
    assert ctx["context"] is None
    assert ctx["session_id"] is None
