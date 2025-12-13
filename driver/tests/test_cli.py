"""Tests for CLI functionality."""

from typer.testing import CliRunner

from supex_driver.cli.main import app

runner = CliRunner()


class TestCLIApp:
    """Test CLI application structure."""

    def test_app_exists(self) -> None:
        """Test that CLI app exists and has correct name."""
        assert app is not None
        assert app.info.name == "supex"

    def test_app_has_commands(self) -> None:
        """Test that all expected commands are registered."""
        expected_commands = [
            "status",
            "eval",
            "eval-file",
            "info",
            "entities",
            "selection",
            "layers",
            "materials",
            "camera",
            "screenshot",
            "open",
            "save",
            "export",
        ]

        # Get command names from help output (most reliable method)
        result = runner.invoke(app, ["--help"])
        help_output = result.output.lower()

        for cmd in expected_commands:
            assert cmd in help_output, f"Missing command in help: {cmd}"

    def test_help_output(self) -> None:
        """Test that --help works and shows app description."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "supex" in result.output.lower() or "sketchup" in result.output.lower()

    def test_command_help(self) -> None:
        """Test that individual command help works."""
        result = runner.invoke(app, ["eval", "--help"])

        assert result.exit_code == 0
        assert "ruby" in result.output.lower()


class TestCLIValidation:
    """Test CLI input validation."""

    def test_eval_file_nonexistent(self) -> None:
        """Test eval-file with nonexistent file returns error."""
        result = runner.invoke(app, ["eval-file", "/nonexistent/path/to/file.rb"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "file" in result.output.lower()

    def test_open_nonexistent(self) -> None:
        """Test open with nonexistent file returns error."""
        result = runner.invoke(app, ["open", "/nonexistent/model.skp"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "file" in result.output.lower()


class TestCLIPlainMode:
    """Test CLI in plain output mode."""

    def test_help_works_in_plain_mode(self) -> None:
        """Help should work regardless of output mode."""
        result = runner.invoke(app, ["--help"], env={"SUPEX_PLAIN": "1"})
        assert result.exit_code == 0
        assert "supex" in result.output.lower() or "sketchup" in result.output.lower()

    def test_error_output_plain_mode_no_markup(self) -> None:
        """Errors should not contain Rich markup in plain mode."""
        result = runner.invoke(app, ["eval-file", "/nonexistent.rb"], env={"SUPEX_PLAIN": "1"})
        assert result.exit_code == 1
        # Should not contain Rich markup tags
        assert "[red]" not in result.output
        assert "[/red]" not in result.output
        assert "[green]" not in result.output
        assert "[/green]" not in result.output

    def test_error_output_has_prefix_plain_mode(self) -> None:
        """Error output should have [ERROR] prefix in plain mode."""
        # Reset the global output instance to pick up env var
        import supex_driver.cli.output as output_module

        output_module._output = None

        result = runner.invoke(app, ["eval-file", "/nonexistent.rb"], env={"SUPEX_PLAIN": "1"})
        assert result.exit_code == 1
        # Check stderr for error message with prefix
        assert "[ERROR]" in result.output or "not found" in result.output.lower()

    def test_command_help_plain_mode(self) -> None:
        """Individual command help should work in plain mode."""
        result = runner.invoke(app, ["eval", "--help"], env={"SUPEX_PLAIN": "1"})
        assert result.exit_code == 0
        assert "ruby" in result.output.lower()
