"""CLI wrapper for e2e tests."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CLIResult:
    """Result from CLI command execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0

    def json(self) -> dict[str, Any]:
        """Parse stdout as JSON."""
        return json.loads(self.stdout)


class CLIRunner:
    """Wrapper around the supex CLI for testing."""

    # Agent name used for client identification in logs
    AGENT_NAME = "e2e-test"

    def __init__(self, driver_path: Path | None = None):
        self._driver_path = driver_path or (
            Path(__file__).parent.parent.parent / "driver"
        )
        self._snippets_loaded = False

    def load_snippets(self) -> CLIResult:
        """Load all Ruby snippet files into SketchUp context.

        Should be called once at the start of the test session.
        Loads all .rb files from tests/snippets/src/ directory.
        """
        if self._snippets_loaded:
            return CLIResult(0, "Snippets already loaded", "")

        loader_path = Path(__file__).parent.parent / "snippets" / "src" / "loader.rb"
        result = self.eval(f"load '{loader_path}'")

        if result.success:
            self._snippets_loaded = True

        return result

    def call_snippet(self, func_name: str, *args) -> CLIResult:
        """Call a Ruby snippet function by name.

        Automatically prefixes the function name with SupexTestSnippets module.

        Args:
            func_name: Name of the Ruby function to call (without module prefix)
            *args: Arguments to pass to the function

        Returns:
            CLIResult with the function's return value

        Example:
            cli.call_snippet('geom_create_cube')  # Calls SupexTestSnippets::geom_create_cube
            cli.call_snippet('some_function', 'arg1', 42)
        """
        # Add module prefix automatically
        full_name = f"SupexTestSnippets::{func_name}"

        # Format arguments for Ruby
        if args:
            # Convert Python values to Ruby format
            ruby_args = []
            for arg in args:
                if isinstance(arg, str):
                    # Escape quotes in strings
                    escaped = arg.replace("'", "\\'")
                    ruby_args.append(f"'{escaped}'")
                elif isinstance(arg, bool):
                    ruby_args.append('true' if arg else 'false')
                elif isinstance(arg, (int, float)):
                    ruby_args.append(str(arg))
                elif arg is None:
                    ruby_args.append('nil')
                else:
                    # For other types, try to convert to string
                    ruby_args.append(str(arg))

            args_str = ', '.join(ruby_args)
            code = f"{full_name}({args_str})"
        else:
            code = f"{full_name}()"

        return self.eval(code)

    def _run(self, *args: str, timeout: float = 30.0) -> CLIResult:
        """Run a supex CLI command."""
        cmd = ["uv", "run", "supex", *args]
        # Pass SUPEX_AGENT to identify as e2e test in logs
        env = {**os.environ, "SUPEX_AGENT": self.AGENT_NAME}
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self._driver_path,
            timeout=timeout,
            env=env,
        )
        return CLIResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def status(self) -> CLIResult:
        """Check SketchUp connection status."""
        return self._run("status")

    def info(self) -> CLIResult:
        """Get model info."""
        return self._run("info")

    def eval(self, code: str) -> CLIResult:
        """Evaluate Ruby code."""
        return self._run("eval", code)

    def entities(self, entity_type: str = "all") -> CLIResult:
        """List entities in the model."""
        return self._run("entities", entity_type)

    def selection(self) -> CLIResult:
        """Get current selection."""
        return self._run("selection")

    def layers(self) -> CLIResult:
        """Get layers/tags."""
        return self._run("layers")

    def materials(self) -> CLIResult:
        """Get materials."""
        return self._run("materials")

    def camera(self) -> CLIResult:
        """Get camera info."""
        return self._run("camera")

    def screenshot(
        self,
        output_path: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> CLIResult:
        """Take a screenshot."""
        args = ["screenshot"]
        if output_path:
            args.extend(["--output", output_path])
        if width:
            args.extend(["--width", str(width)])
        if height:
            args.extend(["--height", str(height)])
        return self._run(*args)

    def open_model(self, path: str) -> CLIResult:
        """Open a model file."""
        return self._run("open", path)

    def save_model(self, path: str | None = None) -> CLIResult:
        """Save the model."""
        args = ["save"]
        if path:
            args.append(path)
        return self._run(*args)

    def export(self, format: str = "skp") -> CLIResult:
        """Export the model."""
        return self._run("export", "--format", format)

    def new_model(self) -> CLIResult:
        """Create a new empty model."""
        # SketchUp API: Sketchup.file_new creates a new model
        return self.eval("Sketchup.file_new")

    def clear_model(self) -> CLIResult:
        """Clear all entities from the current model."""
        return self.call_snippet('fixture_clear_entities')
