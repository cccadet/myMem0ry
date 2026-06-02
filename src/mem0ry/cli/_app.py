from __future__ import annotations

import typer

app = typer.Typer(help="myMem0ry — personal memory search system")


@app.callback(invoke_without_command=True)
def _root() -> None:
    from mem0ry.utils.update_check import check_for_update

    check_for_update()


_HELP_WORKDIR = "Working directory"
_HELP_SESSION = "Session ID"

_DEFAULT_SOURCES = [
    __import__("pathlib").Path("data/openai/export"),
    __import__("pathlib").Path("data/gemini"),
    __import__("pathlib").Path("data/claude"),
]
