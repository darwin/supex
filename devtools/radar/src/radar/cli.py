"""Radar CLI entry point."""

from __future__ import annotations

import asyncio
import os
import tomllib
from pathlib import Path
from typing import Annotated, Optional

import typer

from .tailer import TailSource

app = typer.Typer(
    name="radar",
    help="Supex Radar — single-host log aggregator with TUI",
    add_completion=False,
)

# ---------------------------------------------------------------------------
# Built-in default sources (post-log-layout-unify)
# ---------------------------------------------------------------------------

_DEFAULT_SOURCES: list[dict[str, str]] = [
    {"name": "mcp-protocol", "path": ".tmp/logs/mcp-protocol.jsonl", "parser": "jsonl"},
    {"name": "mcp-stderr", "path": ".tmp/logs/mcp-stderr.log", "parser": "pipe"},
    {"name": "cli-driver", "path": ".tmp/logs/cli-driver.log", "parser": "pipe"},
    {"name": "cli-stdout", "path": ".tmp/logs/cli-stdout.log", "parser": "plain"},
    {"name": "cli-stderr", "path": ".tmp/logs/cli-stderr.log", "parser": "pipe"},
    {"name": "runtime-console", "path": ".tmp/logs/runtime-console.log", "parser": "pipe"},
    {"name": "runtime-stdout", "path": ".tmp/logs/runtime-stdout.log", "parser": "plain"},
    {"name": "runtime-stderr", "path": ".tmp/logs/runtime-stderr.log", "parser": "plain"},
    {"name": "vcad-sidecar", "path": ".tmp/logs/vcad-sidecar-stderr.log", "parser": "pipe"},
    {"name": "vcad-events", "path": ".tmp/logs/vcad-events.jsonl", "parser": "jsonl"},
]


def _resolve_workspace() -> Path:
    """Effective workspace root: $SUPEX_WORKSPACE or cwd."""
    ws = os.environ.get("SUPEX_WORKSPACE")
    return Path(ws) if ws else Path.cwd()


def _resolve_sources(
    mode: str,
    files: list[Path] | None,
    config_path: Path | None,
) -> tuple[list[TailSource], dict[str, str]]:
    """Resolve TailSource list and parser overrides for the selected mode."""
    if mode == "ad-hoc":
        assert files is not None
        sources = [TailSource(source=f.stem, source_path=f) for f in files]
        return sources, {}

    if mode == "config":
        assert config_path is not None
        return _load_config(config_path)

    # Default mode
    workspace = _resolve_workspace()
    sources: list[TailSource] = []
    parser_overrides: dict[str, str] = {}
    for src_def in _DEFAULT_SOURCES:
        path = workspace / src_def["path"]
        sources.append(TailSource(source=src_def["name"], source_path=path))
        parser_overrides[src_def["name"]] = src_def["parser"]
    return sources, parser_overrides


def _load_config(config_path: Path) -> tuple[list[TailSource], dict[str, str]]:
    """Load a TOML config file and resolve sources."""
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    workspace = Path(config.get("workspace", "."))
    if not workspace.is_absolute():
        workspace = (config_path.parent / workspace).resolve()

    sources: list[TailSource] = []
    parser_overrides: dict[str, str] = {}
    for src in config.get("source", []):
        path = workspace / src["path"]
        sources.append(TailSource(source=src["name"], source_path=path))
        if "parser" in src:
            parser_overrides[src["name"]] = src["parser"]
    return sources, parser_overrides


# ---------------------------------------------------------------------------
# Launch helpers
# ---------------------------------------------------------------------------


def _do_watch(
    sources: list[TailSource],
    parser_overrides: dict[str, str],
    *,
    plain: bool,
    pane_name: str,
) -> None:
    """Actually start the ingest pipeline and TUI / plain stream."""
    from .buffer import ObservableBuffer
    from .ingest import IngestPipeline
    from .tailer import MultiTailer

    buffer = ObservableBuffer()
    tailer = MultiTailer(sources)
    pipeline = IngestPipeline(tailer, buffer, parser_overrides=parser_overrides)

    if plain:
        asyncio.run(_run_plain(pipeline, buffer))
    else:
        _run_tui(pipeline, buffer, pane_name)


async def _run_plain(pipeline, buffer) -> None:
    """Stream events to stdout in plain text."""
    from .tui.renderers import render_plain_line

    task = asyncio.create_task(pipeline.run())
    try:
        while True:
            events = buffer.drain_pending()
            for event in events:
                typer.echo(render_plain_line(event))
            await asyncio.sleep(0.1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def _run_tui(pipeline, buffer, pane_name: str) -> None:
    """Launch the Textual TUI application."""
    from .tui.app import RadarApp

    tui_app = RadarApp(pipeline=pipeline, buffer=buffer, pane_name=pane_name)
    tui_app.run()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


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
    pane_name: Annotated[
        str,
        typer.Option("--pane-name", help="tmux pane name (TUI mode)"),
    ] = "radar",
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

    typer.echo(f"[radar] mode={mode}, plain={plain}")

    sources, parser_overrides = _resolve_sources(mode, files, config)
    _do_watch(sources, parser_overrides, plain=plain, pane_name=pane_name)


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
