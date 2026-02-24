"""Radar CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="radar",
    help="Supex Radar — single-host log aggregator with TUI",
    add_completion=False,
)


@app.command()
def watch(
    files: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Ad-hoc log files to watch (skips config/default sources)"),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="TOML config file"),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Plain stdout stream (no TUI)"),
    ] = False,
) -> None:
    """Watch log files with live tail streaming."""
    has_files = bool(files)

    if has_files and config is not None:
        typer.echo(
            "Error: cannot combine ad-hoc files with --config. "
            "Use either positional files or --config, not both.",
            err=True,
        )
        raise typer.Exit(code=1)

    if has_files:
        assert files is not None
        mode = "ad-hoc"
        typer.echo(f"[radar] ad-hoc mode: watching {len(files)} file(s)")
    elif config is not None:
        mode = "config"
        typer.echo(f"[radar] config mode: {config}")
    else:
        mode = "default"
        typer.echo("[radar] default mode: watching standard supex logs")

    # Scaffold placeholder — actual implementation in later phases
    typer.echo(f"[radar] mode={mode}, plain={plain}")


@app.command()
def parse(
    file: Annotated[
        Path,
        typer.Argument(help="Log file to parse and dump"),
    ],
) -> None:
    """Parse a log file and dump structured events (smoke-test helper)."""
    if not file.exists():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(code=1)

    # Scaffold placeholder — actual parser pipeline in later phases
    typer.echo(f"[radar] parse: {file}")


def main() -> None:
    app()
