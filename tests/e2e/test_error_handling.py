"""Tests for error handling and edge cases.

This module tests that the Supex CLI properly handles various error conditions
including Ruby syntax errors, runtime errors, and edge cases.
"""

import pytest

from helpers.cli_runner import CLIRunner


def _get_error_output(result) -> str:
    """Get combined error output from CLI result (errors may be in stdout or stderr)."""
    return result.stdout + result.stderr


class TestRubyEvalErrors:
    """Test error handling for Ruby code evaluation."""

    def test_syntax_error_returns_failure(self, cli: CLIRunner) -> None:
        """Invalid Ruby syntax should return error."""
        result = cli.eval("def broken(")
        assert not result.success
        output = _get_error_output(result).lower()
        assert "syntax" in output or "error" in output

    def test_runtime_error_returns_failure(self, cli: CLIRunner) -> None:
        """Ruby runtime error should be reported."""
        result = cli.eval("raise 'Intentional test error'")
        assert not result.success
        output = _get_error_output(result)
        assert "Intentional test error" in output

    def test_undefined_method_error(self, cli: CLIRunner) -> None:
        """Calling undefined method should error."""
        result = cli.eval("this_method_does_not_exist_xyz()")
        assert not result.success

    def test_error_snippet_runtime(self, cli: CLIRunner) -> None:
        """Error snippet should propagate error."""
        result = cli.call_snippet("error_raise_runtime")
        assert not result.success
        output = _get_error_output(result)
        assert "Intentional test error" in output

    def test_error_does_not_crash_subsequent_commands(self, cli: CLIRunner) -> None:
        """After error, subsequent commands should still work."""
        # Cause an error
        cli.eval("raise 'test'")
        # Next command should work
        result = cli.eval("1 + 1")
        assert result.success
        assert "2" in result.stdout


class TestInvalidInputs:
    """Test handling of invalid inputs."""

    def test_eval_empty_code(self, cli: CLIRunner) -> None:
        """Empty code should not crash."""
        result = cli.eval("")
        # May succeed with nil or fail gracefully
        assert result.exit_code is not None

    def test_eval_whitespace_only(self, cli: CLIRunner) -> None:
        """Whitespace-only code should not crash."""
        result = cli.eval("   \n\t  ")
        assert result.exit_code is not None

    def test_list_entities_invalid_type(self, cli: CLIRunner) -> None:
        """Invalid entity type should be handled."""
        result = cli.entities("nonexistent_type")
        # Should either fail gracefully or return empty
        assert result.exit_code is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_ruby_code(self, cli: CLIRunner) -> None:
        """Long Ruby code should be handled."""
        long_code = "x = 1\n" * 100 + "x"
        result = cli.eval(long_code)
        assert result.success
        assert "1" in result.stdout

    def test_unicode_in_ruby_code(self, cli: CLIRunner) -> None:
        """Unicode should be handled properly."""
        result = cli.eval("'Příliš žluťoučký kůň'")
        assert result.success
        assert "Příliš" in result.stdout

    def test_special_characters_in_strings(self, cli: CLIRunner) -> None:
        """Special characters should be escaped properly."""
        result = cli.eval('"test\\nwith\\nnewlines"')
        assert result.success

    def test_multiline_ruby_code(self, cli: CLIRunner) -> None:
        """Multiline Ruby code should execute correctly."""
        code = """
def test_func
  x = 1
  y = 2
  x + y
end
test_func
"""
        result = cli.eval(code.strip())
        assert result.success
        assert "3" in result.stdout

    def test_ruby_array_output(self, cli: CLIRunner) -> None:
        """Ruby arrays should be returned properly."""
        result = cli.eval("[1, 2, 3]")
        assert result.success
        assert "1" in result.stdout
        assert "2" in result.stdout
        assert "3" in result.stdout

    def test_ruby_hash_output(self, cli: CLIRunner) -> None:
        """Ruby hashes should be returned properly."""
        result = cli.eval("{a: 1, b: 2}.to_json")
        assert result.success
        data = result.json()
        assert data["a"] == 1
        assert data["b"] == 2
