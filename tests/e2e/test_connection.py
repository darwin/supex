"""Connection and basic communication tests."""

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
        assert "2" in result.stdout

    def test_sketchup_version(self, cli: CLIRunner) -> None:
        """Get SketchUp version info."""
        result = cli.eval("Sketchup.version")
        assert result.success, f"Failed to get version: {result.stderr}"
        # Version should be something like "24.0.123"
        assert result.stdout.strip()

    def test_active_model_exists(self, cli: CLIRunner) -> None:
        """Verify active model is available."""
        result = cli.eval("!Sketchup.active_model.nil?")
        assert result.success
        assert "true" in result.stdout.lower()


class TestBasicCommands:
    """Tests for basic CLI commands."""

    def test_info_command(self, cli: CLIRunner) -> None:
        """Test model info command returns valid data."""
        result = cli.info()
        assert result.success, f"Info command failed: {result.stderr}"
        # Should contain model information
        assert result.stdout.strip()

    def test_camera_command(self, cli: CLIRunner) -> None:
        """Test camera info command."""
        result = cli.camera()
        assert result.success, f"Camera command failed: {result.stderr}"

    def test_layers_command(self, cli: CLIRunner) -> None:
        """Test layers command."""
        result = cli.layers()
        assert result.success, f"Layers command failed: {result.stderr}"

    def test_materials_command(self, cli: CLIRunner) -> None:
        """Test materials command."""
        result = cli.materials()
        assert result.success, f"Materials command failed: {result.stderr}"
