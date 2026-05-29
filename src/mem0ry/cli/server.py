from __future__ import annotations

import os
from pathlib import Path

import typer

from ..config import MemoryConfig
from ._app import _HELP_SESSION, _HELP_WORKDIR, app


@app.command(help="Start the MCP / HTTP memory server")
def serve(
    host: str = typer.Option("", "--host", help="Bind address"),
    port: int = typer.Option(0, "--port", "-p", help="Bind port"),
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
) -> None:
    config = MemoryConfig()
    bind_host = host or config.server_host
    bind_port = port or config.server_port

    if detach:
        import subprocess
        import sys

        pid_file = Path(config.server_pid_file)
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        from ..daemon import is_server_running

        if is_server_running():
            typer.echo(f"Server already running at http://{bind_host}:{bind_port}")
            return

        cmd = [
            sys.executable,
            "-m",
            "mem0ry.mcp_server",
        ]
        env = {
            **os.environ,
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": bind_host,
            "MCP_PORT": str(bind_port),
        }
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        pid_file.write_text(str(proc.pid))
        typer.echo(f"Server started (pid {proc.pid}) at http://{bind_host}:{bind_port}")
        return

    os.environ["MCP_TRANSPORT"] = "streamable-http"
    os.environ["MCP_HOST"] = bind_host
    os.environ["MCP_PORT"] = str(bind_port)

    from ..mcp_server import main as mcp_main

    mcp_main()


@app.command(help="Send an observation event to the server (hook entrypoint)")
def observe(
    kind: str = typer.Argument(
        ...,
        help="Event kind: session-start, user-prompt, post-tool-use, pre-compact, session-end",
    ),
    content: str = typer.Argument("", help="Event content (reads stdin if empty)"),
    cwd: str = typer.Option("", "--cwd", help=_HELP_WORKDIR),
    session: str = typer.Option("", "--session", "-s", help=_HELP_SESSION),
    agent: str = typer.Option("manual", "--agent", "-a", help="Agent name"),
) -> None:
    import json
    import sys
    import urllib.error
    import urllib.request

    from ..daemon import ensure_server, get_server_url

    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        if not content:
            content = ""

    ensure_server()
    url = get_server_url()

    payload = {
        "kind": kind,
        "session_id": session or "cli-obs",
        "agent": agent,
        "cwd": cwd or str(Path.cwd()),
        "body": content[:10000] if content else None,
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("MEM0RY_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{url}/hook",
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            result = json.loads(resp.read())
            typer.echo(f"Observed: {result.get('id', '?')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        typer.echo(f"Error {e.code}: {body}", err=True)
    except urllib.error.URLError as e:
        typer.echo(f"Server not reachable: {e}", err=True)
