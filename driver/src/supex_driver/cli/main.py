"""Main CLI entry point for SketchUp automation."""

import json
import logging
import os
from pathlib import Path
from typing import Annotated

import typer

from supex_driver.cli.output import get_output


def _setup_logging():
    """Configure logging to file only (lazy initialization).

    Called once when first needed. Fails gracefully if log directory
    cannot be created.
    """
    workspace = os.environ.get("SUPEX_WORKSPACE", os.path.expanduser("~/.supex/tmp-workspace"))
    default_log_dir = os.path.join(workspace, ".tmp", "logs")
    log_dir = os.environ.get("SUPEX_LOG_DIR", default_log_dir)
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "supex-cli.log")
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            filename=log_file,
            filemode="a",
        )
    except OSError:
        # If we can't create log directory, configure null handler
        logging.basicConfig(level=logging.WARNING, handlers=[logging.NullHandler()])


# Lazy logging setup - only configure when needed
_logging_configured = False


def _ensure_logging():
    """Ensure logging is configured (lazy init)."""
    global _logging_configured
    if not _logging_configured:
        _setup_logging()
        _logging_configured = True

from supex_driver.connection import SketchupConnection, get_sketchup_connection
from supex_driver.connection.exceptions import (
    SketchUpConnectionError,
    SketchUpRemoteError,
)

app = typer.Typer(
    name="supex",
    help="CLI for SketchUp automation via Supex runtime.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Common options
HostOption = Annotated[str, typer.Option("--host", "-H", help="SketchUp host")]
PortOption = Annotated[int, typer.Option("--port", "-p", help="SketchUp port")]


def get_connection(host: str = "localhost", port: int = 9876) -> SketchupConnection:
    """Get a connection to SketchUp."""
    # Allow overriding agent via environment variable (useful for testing)
    agent = os.environ.get("SUPEX_AGENT", "user")
    return get_sketchup_connection(host=host, port=port, agent=agent)


def handle_error(e: Exception, exit_code: int = 1):
    """Handle and display errors."""
    out = get_output()
    if isinstance(e, SketchUpRemoteError):
        out.error(f"SketchUp error [{e.code}]: {e.message}")
        if e.data:
            if "file" in e.data:
                out.info(f"File: {e.data['file']}", dim=True)
            if "line" in e.data:
                out.info(f"Line: {e.data['line']}", dim=True)
            if "hint" in e.data:
                out.info(f"Hint: {e.data['hint']}", dim=True)
    elif isinstance(e, SketchUpConnectionError):
        out.error(f"Connection error: {e}")
        out.info("Make sure SketchUp is running with the Supex runtime.", dim=True)
    else:
        out.error(str(e))
    raise typer.Exit(exit_code)


def print_result(result: dict, as_json: bool = False) -> None:
    """Print command result to console."""
    out = get_output()
    if as_json:
        out.json(result)
    # Pretty print based on content
    elif "success" in result and not result.get("success"):
        out.error(f"Failed: {result.get('error', 'Unknown error')}")
    else:
        out.json(result)


def get_project_root() -> Path:
    """Find project root by looking for CLAUDE.md or .git."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "CLAUDE.md").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


def check_docs_available() -> tuple[bool, Path]:
    """Check if SketchUp API docs are available."""
    project_root = get_project_root()
    docs_path = project_root / "docgen" / "generated-sketchup-api-docs"
    index_path = docs_path / "INDEX.md"
    return index_path.exists(), docs_path


@app.command()
def status(
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Check SketchUp connection and system status."""
    out = get_output()
    sketchup_connected = False

    # SketchUp connection status
    try:
        conn = get_connection(host, port)
        result = conn.send_command("ping")
        version = result.get('version', 'unknown')
        out.panel(
            f"[green]Connected[/green]\nVersion: {version}",
            title="SketchUp Status",
        )
        sketchup_connected = True
    except Exception as e:
        out.panel(
            f"[red]Disconnected[/red]\n{e}",
            title="SketchUp Status",
        )
        out.info("Make sure SketchUp is running with the Supex runtime.", dim=True)

    # Documentation status
    docs_available, docs_path = check_docs_available()
    if docs_available:
        out.print(f"\n[dim]API Docs:[/dim] [green]Available[/green] at {docs_path}")
    else:
        out.print("\n[dim]API Docs:[/dim] [yellow]Not installed[/yellow] (optional)")
        out.info("  Generate with: ./scripts/regenerate-sketchup-api-docs.sh", dim=True)

    # Exit with error only if SketchUp disconnected
    if not sketchup_connected:
        raise typer.Exit(1)


@app.command()
def reload(
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Reload the SketchUp extension without restarting SketchUp."""
    out = get_output()
    try:
        out.warning("Reloading SketchUp extension...")
        conn = get_connection(host, port)
        result = conn.send_command("reload_extension")

        if result.get("success"):
            out.success("Extension reloaded successfully")
            if "message" in result:
                out.print(result["message"])
        else:
            out.error("Failed to reload extension")
            error_msg = result.get("error", "Unknown error")
            out.print(error_msg)
            raise typer.Exit(1)

    except Exception as e:
        handle_error(e)


@app.command("eval")
def eval_ruby(
    code: Annotated[str, typer.Argument(help="Ruby code to execute")],
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """Evaluate Ruby code in SketchUp context."""
    out = get_output()
    try:
        conn = get_connection(host, port)
        result = conn.send_command("eval_ruby", {"code": code})

        if raw:
            print(json.dumps(result))
        else:
            # Extract the actual result text
            content = result.get("content", [])
            if isinstance(content, list) and content:
                text = content[0].get("text", str(result))
                out.print(text)
            else:
                out.print(result.get("result", str(result)))
    except Exception as e:
        handle_error(e)


@app.command("eval-file")
def eval_ruby_file(
    file_path: Annotated[Path, typer.Argument(help="Path to Ruby file")],
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """Evaluate Ruby code from a file in SketchUp context."""
    out = get_output()
    # Resolve to absolute path
    abs_path = file_path.resolve()

    if not abs_path.exists():
        out.error(f"File not found: {abs_path}")
        raise typer.Exit(1)

    try:
        conn = get_connection(host, port)
        result = conn.send_command("eval_ruby_file", {"file_path": str(abs_path)})

        if raw:
            print(json.dumps(result))
        elif result.get("success"):
            out.success(f"Executed {abs_path.name}")
            content = result.get("content", [])
            if isinstance(content, list) and content:
                text = content[0].get("text", "")
                if text:
                    out.print(text)
        else:
            out.error(f"{result.get('error', 'Unknown error')}")
    except Exception as e:
        handle_error(e)


@app.command()
def info(
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """Get information about the current SketchUp model."""
    out = get_output()
    try:
        conn = get_connection(host, port)
        result = conn.send_command("get_model_info")

        if raw:
            print(json.dumps(result))
        else:
            content = result.get("content", [{}])
            if isinstance(content, list) and content:
                data = json.loads(content[0].get("text", "{}"))
            else:
                data = result

            out.table(data, title="Model Info")
    except Exception as e:
        handle_error(e)


@app.command()
def entities(
    entity_type: Annotated[str, typer.Argument(help="Type: all, faces, edges, groups, components")] = "all",
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """List entities in the model."""
    try:
        conn = get_connection(host, port)
        result = conn.send_command("list_entities", {"entity_type": entity_type})

        if raw:
            print(json.dumps(result))
        else:
            print_result(result)
    except Exception as e:
        handle_error(e)


@app.command()
def selection(
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """Get currently selected entities in SketchUp."""
    try:
        conn = get_connection(host, port)
        result = conn.send_command("get_selection")

        if raw:
            print(json.dumps(result))
        else:
            print_result(result)
    except Exception as e:
        handle_error(e)


@app.command()
def layers(
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """List layers (tags) in the model."""
    try:
        conn = get_connection(host, port)
        result = conn.send_command("get_layers")

        if raw:
            print(json.dumps(result))
        else:
            print_result(result)
    except Exception as e:
        handle_error(e)


@app.command()
def materials(
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """List materials in the model."""
    try:
        conn = get_connection(host, port)
        result = conn.send_command("get_materials")

        if raw:
            print(json.dumps(result))
        else:
            print_result(result)
    except Exception as e:
        handle_error(e)


@app.command()
def camera(
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """Get current camera position and settings."""
    try:
        conn = get_connection(host, port)
        result = conn.send_command("get_camera_info")

        if raw:
            print(json.dumps(result))
        else:
            print_result(result)
    except Exception as e:
        handle_error(e)


@app.command()
def screenshot(
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
    width: Annotated[int, typer.Option("--width", "-w", help="Image width")] = 1920,
    height: Annotated[int, typer.Option("--height", help="Image height")] = 1080,
    transparent: Annotated[bool, typer.Option("--transparent", "-t", help="Transparent background")] = False,
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Take a screenshot of the current SketchUp view."""
    out = get_output()
    try:
        conn = get_connection(host, port)
        params: dict[str, int | bool | str] = {
            "width": width,
            "height": height,
            "transparent": transparent,
        }
        if output:
            params["output_path"] = str(output.resolve())

        result = conn.send_command("take_screenshot", params)

        content = result.get("content", [{}])
        if isinstance(content, list) and content:
            data = json.loads(content[0].get("text", "{}"))
        else:
            data = result

        file_path = data.get("file_path", "unknown")
        out.success(f"Screenshot saved to: {file_path}")
    except Exception as e:
        handle_error(e)


@app.command("open")
def open_model(
    path: Annotated[Path, typer.Argument(help="Path to .skp file")],
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Open a SketchUp model file."""
    out = get_output()
    abs_path = path.resolve()

    if not abs_path.exists():
        out.error(f"File not found: {abs_path}")
        raise typer.Exit(1)

    try:
        conn = get_connection(host, port)
        conn.send_command("open_model", {"path": str(abs_path)})
        out.success(f"Opened: {abs_path.name}")
    except Exception as e:
        handle_error(e)


@app.command()
def save(
    path: Annotated[Path | None, typer.Argument(help="Path to save to (optional)")] = None,
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Save the current SketchUp model."""
    out = get_output()
    try:
        conn = get_connection(host, port)
        params = {}
        if path:
            params["path"] = str(path.resolve())

        conn.send_command("save_model", params)
        out.success("Model saved")
    except Exception as e:
        handle_error(e)


@app.command()
def export(
    format: Annotated[str, typer.Argument(help="Export format: skp, obj, dae, stl, png, jpg")] = "skp",
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Export the current SketchUp scene."""
    out = get_output()
    try:
        conn = get_connection(host, port)
        result = conn.send_command("export_scene", {"format": format})

        # Handle both MCP format (content array) and direct format (file_path)
        content = result.get("content")
        if isinstance(content, list) and content:
            data = json.loads(content[0].get("text", "{}"))
        else:
            data = result

        file_path = data.get("file_path", "unknown")
        out.success(f"Exported to: {file_path}")
    except Exception as e:
        handle_error(e)


def main():
    """Main entry point."""
    _ensure_logging()
    try:
        app()
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
