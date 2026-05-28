from __future__ import annotations

from pathlib import Path

import typer

from ._app import app


def _hooks_dir() -> Path:
    import mem0ry
    pkg_dir = Path(mem0ry.__file__).parent
    candidate = pkg_dir / "hooks"
    if candidate.is_dir():
        return candidate.resolve()
    for parent in pkg_dir.parents:
        candidate = parent / "hooks"
        if candidate.is_dir():
            return candidate.resolve()
    msg = "Could not locate hooks/ directory. Reinstall myMem0ry or clone the repo."
    typer.echo(msg, err=True)
    raise typer.Exit(code=1)


@app.command()
def hooks(
    path: bool = typer.Option(False, "--path", "-p", help="Print path to hooks directory"),
    install: bool = typer.Option(False, "--install", "-i", help="Install hooks for the current agent"),
    config: bool = typer.Option(False, "--config", "-c", help="Print settings.json snippet for Claude Code"),
) -> None:
    from shutil import copy2

    hooks_dir = _hooks_dir()

    if path:
        typer.echo(str(hooks_dir))
        return

    if config:
        start_sh = hooks_dir / "claude-code" / "session-start.sh"
        hook_sh = hooks_dir / "claude-code" / "mymem0ry-hook.sh"
        typer.echo("Add this to your ~/.claude/settings.json:\n")
        typer.echo("```json")
        typer.echo('{')
        typer.echo('  "hooks": {')
        typer.echo('    "SessionStart": [{')
        typer.echo(f'      "hooks": [{{"type": "command", "command": "{start_sh}"}}]')
        typer.echo('    }],')
        typer.echo('    "PostToolUse": [{')
        typer.echo('      "matcher": "",')
        typer.echo(f'      "hooks": [{{"type": "command", "command": "{hook_sh} PostToolUse"}}]')
        typer.echo('    }]')
        typer.echo('  }')
        typer.echo('}')
        typer.echo("```")
        return

    if install:
        typer.echo("Detecting agent...")
        agent_dir = _detect_agent_dir()
        if agent_dir is None:
            typer.echo("Could not detect agent config directory.", err=True)
            raise typer.Exit(code=1)
        agent_name = agent_dir.name
        agent_hooks = hooks_dir / agent_name
        if not agent_hooks.is_dir():
            typer.echo(f"No hooks found for {agent_name} at {agent_hooks}", err=True)
            raise typer.Exit(code=1)

        if agent_name == "opencode":
            target = _opencode_hooks_dir()
            target.mkdir(parents=True, exist_ok=True)
            for f in agent_hooks.iterdir():
                copy2(str(f), str(target / f.name))
                target_path = target / f.name
                target_path.chmod(0o755)
                typer.echo(f"  Installed: {target_path}")
            typer.echo(f"\nHooks installed to {target}")
        elif agent_name == "claude-code":
            typer.echo("For Claude Code, run with --config to see the settings.json snippet.")
            typer.echo("Then copy the hooks manually:")
            typer.echo(f"  cp -r {agent_hooks}/* ~/.local/share/mymem0ry/hooks/claude-code/")
        else:
            typer.echo(f"Installation not automated for {agent_name}.")
            typer.echo(f"Hooks are at: {agent_hooks}")
        return

    typer.echo("Usage:")
    typer.echo(f"  mymem0ry hooks --path          # {hooks_dir}")
    typer.echo("  mymem0ry hooks --config        # Print settings.json snippet")
    typer.echo("  mymem0ry hooks --install       # Install for detected agent")


def _detect_agent_dir() -> Path | None:
    home = Path.home()
    claude_cfg = home / ".claude" / "settings.json"
    opencode_cfg = home / ".config" / "opencode" / "opencode.json"
    codex_cfg = home / ".codex" / "config.toml"

    if claude_cfg.exists():
        return home / ".claude"
    if opencode_cfg.exists():
        return home / ".config" / "opencode"
    if codex_cfg.exists():
        return home / ".codex"
    return None


def _opencode_hooks_dir() -> Path:
    for parent in [Path.cwd(), Path.home() / ".config" / "opencode"]:
        candidate = parent / ".opencode" / "hooks"
        if candidate.is_dir() or not parent.name.startswith("."):
            return candidate
    return Path.cwd() / ".opencode" / "hooks"
