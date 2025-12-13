"""Main CLI entry point for SketchUp automation."""

import json
import logging
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

# Configure logging to file only (suppress console output)
_log_dir = os.environ.get("SUPEX_LOG_DIR", os.path.expanduser("~/.supex/logs"))
os.makedirs(_log_dir, exist_ok=True)
_cli_log_file = os.path.join(_log_dir, "cli.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=_cli_log_file,
    filemode="a",
)

from supex_driver.connection import SketchupConnection, get_sketchup_connection
from supex_driver.connection.exceptions import SketchUpConnectionError

app = typer.Typer(
    name="supex",
    help="CLI for SketchUp automation via Supex runtime.",
    no_args_is_help=True,
)
console = Console()

# Common options
HostOption = Annotated[str, typer.Option("--host", "-h", help="SketchUp host")]
PortOption = Annotated[int, typer.Option("--port", "-p", help="SketchUp port")]


def get_connection(host: str = "localhost", port: int = 9876) -> SketchupConnection:
    """Get a connection to SketchUp."""
    # Allow overriding agent via environment variable (useful for testing)
    agent = os.environ.get("SUPEX_AGENT", "user")
    return get_sketchup_connection(host=host, port=port, agent=agent)


def handle_error(e: Exception, exit_code: int = 1):
    """Handle and display errors."""
    if isinstance(e, SketchUpConnectionError):
        console.print(f"[red]Connection error:[/red] {e}")
        console.print("[dim]Make sure SketchUp is running with the Supex runtime.[/dim]")
    else:
        console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(exit_code)


def print_result(result: dict, as_json: bool = False) -> None:
    """Print command result to console."""
    if as_json:
        console.print(JSON(json.dumps(result)))
    # Pretty print based on content
    elif "success" in result and not result.get("success"):
        console.print(f"[red]Failed:[/red] {result.get('error', 'Unknown error')}")
    else:
        console.print(JSON(json.dumps(result)))


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
    sketchup_connected = False

    # SketchUp connection status
    try:
        conn = get_connection(host, port)
        result = conn.send_command("ping")
        version = result.get('version', 'unknown')
        console.print(Panel(
            f"[green]Connected[/green]\nVersion: {version}",
            title="SketchUp Status",
        ))
        sketchup_connected = True
    except Exception as e:
        console.print(Panel(
            f"[red]Disconnected[/red]\n{e}",
            title="SketchUp Status",
        ))
        console.print("[dim]Make sure SketchUp is running with the Supex runtime.[/dim]")

    # Documentation status
    docs_available, docs_path = check_docs_available()
    if docs_available:
        console.print(f"\n[dim]API Docs:[/dim] [green]Available[/green] at {docs_path}")
    else:
        console.print("\n[dim]API Docs:[/dim] [yellow]Not installed[/yellow] (optional)")
        console.print("[dim]  Generate with: ./scripts/regenerate-sketchup-api-docs.sh[/dim]")

    # Exit with error only if SketchUp disconnected
    if not sketchup_connected:
        raise typer.Exit(1)


@app.command()
def reload(
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Reload the SketchUp extension without restarting SketchUp."""
    try:
        console.print("[yellow]Reloading SketchUp extension...[/yellow]")
        conn = get_connection(host, port)
        result = conn.send_command("reload_extension")

        if result.get("success"):
            console.print("[green]Extension reloaded successfully[/green]")
            if "message" in result:
                console.print(result["message"])
        else:
            console.print("[red]Failed to reload extension[/red]")
            error_msg = result.get("error", "Unknown error")
            console.print(error_msg)
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
                console.print(text)
            else:
                console.print(result.get("result", str(result)))
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
    # Resolve to absolute path
    abs_path = file_path.resolve()

    if not abs_path.exists():
        console.print(f"[red]File not found:[/red] {abs_path}")
        raise typer.Exit(1)

    try:
        conn = get_connection(host, port)
        result = conn.send_command("eval_ruby_file", {"file_path": str(abs_path)})

        if raw:
            print(json.dumps(result))
        elif result.get("success"):
            console.print(f"[green]✓[/green] Executed {abs_path.name}")
            content = result.get("content", [])
            if isinstance(content, list) and content:
                text = content[0].get("text", "")
                if text:
                    console.print(text)
        else:
            console.print(f"[red]✗[/red] {result.get('error', 'Unknown error')}")
    except Exception as e:
        handle_error(e)


@app.command()
def info(
    host: HostOption = "localhost",
    port: PortOption = 9876,
    raw: Annotated[bool, typer.Option("--raw", "-r", help="Output raw JSON")] = False,
):
    """Get information about the current SketchUp model."""
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

            table = Table(title="Model Info")
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            for key, value in data.items():
                table.add_row(key, str(value))

            console.print(table)
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
        console.print(f"[green]✓[/green] Screenshot saved to: {file_path}")
    except Exception as e:
        handle_error(e)


@app.command("open")
def open_model(
    path: Annotated[Path, typer.Argument(help="Path to .skp file")],
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Open a SketchUp model file."""
    abs_path = path.resolve()

    if not abs_path.exists():
        console.print(f"[red]File not found:[/red] {abs_path}")
        raise typer.Exit(1)

    try:
        conn = get_connection(host, port)
        conn.send_command("open_model", {"path": str(abs_path)})
        console.print(f"[green]✓[/green] Opened: {abs_path.name}")
    except Exception as e:
        handle_error(e)


@app.command()
def save(
    path: Annotated[Path | None, typer.Argument(help="Path to save to (optional)")] = None,
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Save the current SketchUp model."""
    try:
        conn = get_connection(host, port)
        params = {}
        if path:
            params["path"] = str(path.resolve())

        conn.send_command("save_model", params)
        console.print("[green]✓[/green] Model saved")
    except Exception as e:
        handle_error(e)


@app.command()
def export(
    format: Annotated[str, typer.Argument(help="Export format: skp, obj, dae, stl, png, jpg")] = "skp",
    host: HostOption = "localhost",
    port: PortOption = 9876,
):
    """Export the current SketchUp scene."""
    try:
        conn = get_connection(host, port)
        result = conn.send_command("export_scene", {"format": format})

        content = result.get("content", [{}])
        if isinstance(content, list) and content:
            data = json.loads(content[0].get("text", "{}"))
        else:
            data = result

        file_path = data.get("file_path", "unknown")
        console.print(f"[green]✓[/green] Exported to: {file_path}")
    except Exception as e:
        handle_error(e)


def main():
    """Main entry point."""
    try:
        app()
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
