"""File operations tests - export, open, save.

Tests for file-related operations including export to various formats,
opening model files, and saving models.
"""

import os
import re
from pathlib import Path

import pytest

from helpers.cli_runner import CLIRunner


def get_project_temp_dir(subpath: str = "") -> Path:
    """Get path to project .tmp directory, creating subdirs if needed."""
    project_root = Path(__file__).parent.parent.parent
    temp_dir = project_root / ".tmp" / subpath
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def extract_path_from_output(output: str) -> str | None:
    """Extract file path from CLI output like 'Exported to: /path/to/file'.

    The CLI uses Rich formatting, so we need to handle ANSI escape codes.
    """
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_output = ansi_escape.sub('', output)

    match = re.search(r"Exported to:\s*(.+)$", clean_output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


class TestExportScene:
    """Tests for export_scene functionality."""

    def test_export_skp_format(self, populated_model: CLIRunner) -> None:
        """Export model as SKP format."""
        result = populated_model.export("skp")
        assert result.success, f"Export SKP failed: {result.stderr}"
        assert "Exported to:" in result.stdout

        file_path = extract_path_from_output(result.stdout)
        assert file_path is not None, "Could not extract file path from output"
        assert file_path.endswith(".skp")
        assert os.path.exists(file_path), f"File not found: {file_path}"

    def test_export_obj_format(self, populated_model: CLIRunner) -> None:
        """Export model as OBJ format."""
        result = populated_model.export("obj")
        assert result.success, f"Export OBJ failed: {result.stderr}"
        assert "Exported to:" in result.stdout

        file_path = extract_path_from_output(result.stdout)
        assert file_path is not None
        assert file_path.endswith(".obj")
        assert os.path.exists(file_path)

    def test_export_stl_format(self, populated_model: CLIRunner) -> None:
        """Export model as STL format."""
        result = populated_model.export("stl")
        assert result.success, f"Export STL failed: {result.stderr}"
        assert "Exported to:" in result.stdout

        file_path = extract_path_from_output(result.stdout)
        assert file_path is not None
        assert file_path.endswith(".stl")
        assert os.path.exists(file_path)

    def test_export_png_format(self, populated_model: CLIRunner) -> None:
        """Export model as PNG image."""
        result = populated_model.export("png")
        assert result.success, f"Export PNG failed: {result.stderr}"
        assert "Exported to:" in result.stdout

        file_path = extract_path_from_output(result.stdout)
        assert file_path is not None
        assert file_path.endswith(".png")
        assert os.path.exists(file_path)

    def test_export_jpg_format(self, populated_model: CLIRunner) -> None:
        """Export model as JPG image."""
        result = populated_model.export("jpg")
        assert result.success, f"Export JPG failed: {result.stderr}"
        assert "Exported to:" in result.stdout

        file_path = extract_path_from_output(result.stdout)
        assert file_path is not None
        # JPG gets converted to JPEG extension
        assert file_path.endswith(".jpeg") or file_path.endswith(".jpg")
        assert os.path.exists(file_path)

    def test_export_invalid_format_fails(self, populated_model: CLIRunner) -> None:
        """Export with invalid format should fail gracefully."""
        result = populated_model.export("xyz")
        # Should fail with error
        assert not result.success or "error" in result.stdout.lower() or "error" in result.stderr.lower()


class TestSaveModel:
    """Tests for save_model functionality."""

    def test_save_model_to_path(self, fresh_model: CLIRunner) -> None:
        """Save model to a specific path."""
        temp_dir = get_project_temp_dir("tests/e2e/models")
        save_path = temp_dir / "test_save_model.skp"

        # Create some geometry first
        fresh_model.call_snippet("geom_create_cube")

        result = fresh_model.save_model(str(save_path))
        assert result.success, f"Save model failed: {result.stderr}"
        assert save_path.exists(), f"File was not created at {save_path}"

    def test_save_model_preserves_geometry(self, fresh_model: CLIRunner) -> None:
        """Verify saved model preserves geometry."""
        temp_dir = get_project_temp_dir("tests/e2e/models")
        save_path = temp_dir / "test_preserve_geometry.skp"

        # Create geometry (creates a group with faces)
        fresh_model.call_snippet("geom_create_cube")

        # Count groups (geometry is in a group)
        result = fresh_model.eval("Sketchup.active_model.entities.grep(Sketchup::Group).count")
        original_groups = int(result.stdout.strip())
        assert original_groups > 0, "Should have groups before save"

        # Save model
        fresh_model.save_model(str(save_path))
        assert save_path.exists()

        # File size should be non-trivial
        assert save_path.stat().st_size > 1000, "Saved file should have content"


class TestOpenModel:
    """Tests for open_model functionality."""

    def test_open_existing_model(self, cli: CLIRunner) -> None:
        """Open an existing model file."""
        # First save a model with known content
        temp_dir = get_project_temp_dir("tests/e2e/models")
        model_path = temp_dir / "test_open_model.skp"

        # Create and save a model with geometry
        cli.call_snippet("fixture_clear_all")
        cli.call_snippet("geom_create_cube")
        cli.save_model(str(model_path))

        # Clear the model
        cli.call_snippet("fixture_clear_all")

        # Verify model is empty (no groups)
        result = cli.eval("Sketchup.active_model.entities.grep(Sketchup::Group).count")
        assert result.stdout.strip() == "0", "Model should be empty after clear"

        # Open the saved model
        result = cli.open_model(str(model_path))
        assert result.success, f"Open model failed: {result.stderr}"

        # Verify geometry was loaded (has groups)
        result = cli.eval("Sketchup.active_model.entities.grep(Sketchup::Group).count")
        groups = int(result.stdout.strip())
        assert groups > 0, "Opened model should have geometry"

    def test_open_nonexistent_file_fails(self, cli: CLIRunner) -> None:
        """Opening a nonexistent file should fail gracefully."""
        result = cli.open_model("/nonexistent/path/model.skp")
        # Should fail
        assert not result.success or "error" in result.stdout.lower() or "error" in result.stderr.lower()


class TestReconnect:
    """Tests for connection resilience.

    Note: Full reconnect-after-restart testing requires stopping and
    restarting SketchUp, which is slow. These tests verify the connection
    can recover from transient issues.
    """

    def test_multiple_sequential_commands(self, cli: CLIRunner) -> None:
        """Verify connection handles many sequential commands."""
        for i in range(20):
            result = cli.eval(f"{i} + 1")
            assert result.success, f"Command {i} failed: {result.stderr}"
            assert result.stdout.strip() == str(i + 1)

    def test_commands_after_model_operations(self, fresh_model: CLIRunner) -> None:
        """Connection works after file operations."""
        temp_dir = get_project_temp_dir("tests/e2e/models")
        model_path = temp_dir / "test_reconnect_ops.skp"

        # Save model
        fresh_model.call_snippet("geom_create_cube")
        fresh_model.save_model(str(model_path))

        # Connection should still work
        result = fresh_model.status()
        assert result.success, "Status should work after save"

        # Open model
        fresh_model.open_model(str(model_path))

        # Connection should still work
        result = fresh_model.eval("1 + 1")
        assert result.success, "Eval should work after open"
        assert result.stdout.strip() == "2"

    def test_commands_after_export(self, populated_model: CLIRunner) -> None:
        """Connection works after export operations."""
        # Export in different formats
        populated_model.export("skp")
        populated_model.export("png")

        # Connection should still work
        result = populated_model.status()
        assert result.success, "Status should work after exports"

        result = populated_model.eval("'hello'.upcase")
        assert result.success, "Eval should work after exports"
        assert "HELLO" in result.stdout
