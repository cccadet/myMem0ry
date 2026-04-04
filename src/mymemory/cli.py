from __future__ import annotations

import typer

app = typer.Typer(help="myMem0ry importer CLI")


@app.command()
def version() -> None:
    """Show the current package version."""
    typer.echo("mymem0ry 0.1.0")


def main() -> None:
    """Entry point used by the project script."""
    app()


if __name__ == "__main__":
    main()
