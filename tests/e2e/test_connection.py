"""Connection and basic communication tests.

Tests for basic SketchUp connection and CLI command execution.
"""

import pytest

from helpers.cli_runner import CLIRunner


class TestConnection:
    """Tests for basic SketchUp connection."""

    def test_sketchup_status(self, cli: CLIRunner) -> None:
        """Verify that supex status reports connected."""
        result = cli.status()
        assert result.success, f"Status command failed: {result.stderr}"
        assert "connected" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_ping_via_eval(self, cli: CLIRunner) -> None:
        """Verify basic Ruby eval works."""
        result = cli.eval("1 + 1")
        assert result.success, f"Eval failed: {result.stderr}"
        assert result.stdout.strip() == "2", f"Expected '2', got '{result.stdout.strip()}'"

    def test_sketchup_version(self, cli: CLIRunner) -> None:
        """Get SketchUp version info."""
        result = cli.eval("Sketchup.version")
        assert result.success, f"Failed to get version: {result.stderr}"
        # Version should be something like "24.0.123"
        version = result.stdout.strip()
        assert version, "Version should not be empty"
        assert "." in version, f"Version should contain '.', got '{version}'"

    def test_active_model_exists(self, cli: CLIRunner) -> None:
        """Verify active model is available."""
        result = cli.eval("!Sketchup.active_model.nil?")
        assert result.success
        assert result.stdout.strip().lower() == "true", f"Expected 'true', got '{result.stdout.strip()}'"


class TestBasicCommands:
    """Tests for basic CLI commands using parametrization."""

    @pytest.mark.parametrize("command", ["info", "camera", "layers", "materials"])
    def test_basic_command_succeeds(self, cli: CLIRunner, command: str) -> None:
        """Basic CLI commands should execute successfully."""
        method = getattr(cli, command)
        result = method()
        assert result.success, f"{command} command failed: {result.stderr}"

    def test_info_returns_content(self, cli: CLIRunner) -> None:
        """Info command should return model information."""
        result = cli.info()
        assert result.success, f"Info command failed: {result.stderr}"
        assert result.stdout.strip(), "Info should return content"

    def test_camera_returns_content(self, cli: CLIRunner) -> None:
        """Camera command should return camera information."""
        result = cli.camera()
        assert result.success, f"Camera command failed: {result.stderr}"
        assert result.stdout.strip(), "Camera should return content"
