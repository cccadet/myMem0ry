"""Git-based sync commands for myMem0ry."""

from __future__ import annotations

from pathlib import Path

import typer

from ..config import MemoryConfig
from ..db.git_sync import (
    GitSyncError,
    git_commit_all,
    git_pull,
    git_push,
    git_status,
    is_git_repo,
)
from ._app import app

git_sync_app = typer.Typer(help="Git-based sync for the data directory (experimental)")
app.add_typer(git_sync_app, name="git-sync")


def _repo_dir_from_config(config: MemoryConfig) -> Path:
    """Return the configured git-sync directory, defaulting to the data dir."""
    if config.git_sync_dir:
        return Path(config.git_sync_dir).expanduser().resolve()
    return Path(config.db_path).resolve().parent


@git_sync_app.command(help="Pull the latest changes from the configured remote")
def pull(
    remote: str = typer.Option(None, "--remote", "-r", help="Remote name"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch to pull"),
) -> None:
    config = MemoryConfig()
    repo_dir = _repo_dir_from_config(config)

    if not is_git_repo(repo_dir):
        typer.echo(f"Not a git repository: {repo_dir}", err=True)
        raise typer.Exit(code=1)

    try:
        result = git_pull(repo_dir, remote or config.git_sync_remote, branch or config.git_sync_branch)
        typer.echo(result)
    except GitSyncError as exc:
        typer.echo(f"Pull failed: {exc}", err=True)
        raise typer.Exit(code=1)


@git_sync_app.command(help="Commit any local changes and push to the configured remote")
def push(
    remote: str = typer.Option(None, "--remote", "-r", help="Remote name"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch to push"),
    message: str = typer.Option("manual: myMem0ry git-sync", "--message", "-m", help="Commit message"),
) -> None:
    config = MemoryConfig()
    repo_dir = _repo_dir_from_config(config)

    if not is_git_repo(repo_dir):
        typer.echo(f"Not a git repository: {repo_dir}", err=True)
        raise typer.Exit(code=1)

    try:
        commit = git_commit_all(repo_dir, message)
        if commit:
            result = git_push(repo_dir, remote or config.git_sync_remote, branch or config.git_sync_branch)
            typer.echo(f"Committed {commit} and {result}")
        else:
            result = git_push(repo_dir, remote or config.git_sync_remote, branch or config.git_sync_branch)
            typer.echo(f"Nothing to commit; {result}")
    except GitSyncError as exc:
        typer.echo(f"Push failed: {exc}", err=True)
        raise typer.Exit(code=1)


@git_sync_app.command(help="Show git repository status")
def status() -> None:
    config = MemoryConfig()
    repo_dir = _repo_dir_from_config(config)
    info = git_status(repo_dir)

    if not info["enabled"]:
        typer.echo(f"Git sync disabled: {info['reason']}")
        return

    typer.echo(f"Repository: {repo_dir}")
    typer.echo(f"Branch: {info['branch']}")
    typer.echo(f"Remote: {info['remote'] or '(none)'}")
    typer.echo(f"Clean: {info['clean']}")
    if info["changes"]:
        typer.echo("Changes:")
        for change in info["changes"]:
            typer.echo(f"  {change}")
