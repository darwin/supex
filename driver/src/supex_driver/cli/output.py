"""Output abstraction for CLI supporting both rich and plain modes."""

import json as json_module
import os
import re
import sys
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table


def _should_use_plain_output() -> bool:
    """Determine if plain (non-rich) output should be used.

    Priority order (highest first):
    1. SUPEX_PLAIN=1 -> plain mode (project-specific)
    2. SUPEX_COLOR=1 -> rich mode (project-specific)
    3. NO_COLOR (any non-empty value) -> plain mode (standard)
    4. FORCE_COLOR (any non-empty value) -> rich mode (standard)
    5. TTY detection -> rich if TTY, plain otherwise
    """
    # Project-specific overrides (highest priority)
    if os.environ.get("SUPEX_PLAIN") == "1":
        return True
    if os.environ.get("SUPEX_COLOR") == "1":
        return False

    # Standard environment variables
    no_color = os.environ.get("NO_COLOR", "")
    if no_color:  # Any non-empty value
        return True

    force_color = os.environ.get("FORCE_COLOR", "")
    if force_color:  # Any non-empty value
        return False

    # TTY detection fallback
    return not sys.stdout.isatty()


def _strip_markup(text: str) -> str:
    """Remove Rich markup tags from text.

    Handles tags like [green], [/green], [red], [dim], etc.
    Preserves unicode characters (checkmarks, etc.).
    """
    return re.sub(r"\[/?[a-zA-Z_]+\]", "", text)


class Output:
    """Unified output interface supporting both rich and plain modes."""

    def __init__(self) -> None:
        self._plain_mode = _should_use_plain_output()
        if not self._plain_mode:
            # Use wide console to prevent truncation in non-terminal contexts
            self._console: Console | None = Console(width=200)
        else:
            self._console = None

    @property
    def is_plain(self) -> bool:
        """Return True if plain output mode is active."""
        return self._plain_mode

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print text, stripping Rich markup in plain mode."""
        if self._plain_mode:
            # Convert args to plain text
            text = " ".join(_strip_markup(str(arg)) for arg in args)
            print(text)
        else:
            assert self._console is not None
            self._console.print(*args, **kwargs)

    def success(self, message: str) -> None:
        """Print success message with checkmark."""
        if self._plain_mode:
            print(f"[OK] {message}")
        else:
            assert self._console is not None
            self._console.print(f"[green]\u2713[/green] {message}")

    def error(self, message: str) -> None:
        """Print error message."""
        if self._plain_mode:
            print(f"[ERROR] {message}", file=sys.stderr)
        else:
            assert self._console is not None
            self._console.print(f"[red]Error:[/red] {message}")

    def warning(self, message: str) -> None:
        """Print warning message."""
        if self._plain_mode:
            print(f"[WARN] {message}")
        else:
            assert self._console is not None
            self._console.print(f"[yellow]{message}[/yellow]")

    def info(self, message: str, dim: bool = False) -> None:
        """Print informational message."""
        if self._plain_mode:
            print(message)
        else:
            assert self._console is not None
            if dim:
                self._console.print(f"[dim]{message}[/dim]")
            else:
                self._console.print(message)

    def panel(self, content: str, title: str | None = None) -> None:
        """Print content in a panel (or plain section in plain mode)."""
        if self._plain_mode:
            # Strip markup from content
            plain_content = _strip_markup(content)
            if title:
                separator = "-" * (len(title) + 8)
                print(f"--- {title} ---")
                print(plain_content)
                print(separator)
            else:
                print(plain_content)
        else:
            assert self._console is not None
            self._console.print(Panel(content, title=title))

    def table(self, data: dict[str, Any], title: str | None = None) -> None:
        """Print key-value data as table or plain text."""
        if self._plain_mode:
            if title:
                print(f"{title}:")
            max_key_len = max(len(str(k)) for k in data) if data else 0
            for key, value in data.items():
                print(f"  {key:<{max_key_len}}  {value}")
        else:
            assert self._console is not None
            table = Table(title=title)
            table.add_column("Property", style="cyan")
            table.add_column("Value")
            for key, value in data.items():
                table.add_row(str(key), str(value))
            self._console.print(table)

    def json(self, data: Any) -> None:
        """Print JSON data with or without syntax highlighting."""
        if self._plain_mode:
            print(json_module.dumps(data, indent=2))
        else:
            assert self._console is not None
            self._console.print(JSON(json_module.dumps(data)))


# Global output instance (initialized on first use)
_output: Output | None = None


def get_output() -> Output:
    """Get the global Output instance."""
    global _output
    if _output is None:
        _output = Output()
    return _output
