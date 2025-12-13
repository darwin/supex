"""Tests for CLI output modes."""

import os
import sys
from unittest.mock import patch


class TestShouldUsePlainOutput:
    """Test environment variable and TTY detection for output mode."""

    def test_supex_plain_forces_plain_mode(self) -> None:
        """SUPEX_PLAIN=1 should force plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is True

    def test_supex_color_forces_rich_mode(self) -> None:
        """SUPEX_COLOR=1 should force rich mode."""
        with patch.dict(os.environ, {"SUPEX_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is False

    def test_supex_plain_overrides_supex_color(self) -> None:
        """SUPEX_PLAIN should take priority over SUPEX_COLOR."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1", "SUPEX_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is True

    def test_no_color_enables_plain(self) -> None:
        """NO_COLOR should enable plain mode."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is True

    def test_no_color_empty_value_ignored(self) -> None:
        """NO_COLOR with empty value should be ignored (fall through to TTY)."""
        with patch.dict(os.environ, {"NO_COLOR": ""}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            # Should fall through to TTY detection
            # In test environment, stdout is likely not a TTY
            result = _should_use_plain_output()
            assert result == (not sys.stdout.isatty())

    def test_force_color_enables_rich(self) -> None:
        """FORCE_COLOR should enable rich mode."""
        with patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is False

    def test_no_color_overrides_force_color(self) -> None:
        """NO_COLOR should take priority over FORCE_COLOR."""
        with patch.dict(os.environ, {"NO_COLOR": "1", "FORCE_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is True

    def test_supex_color_overrides_no_color(self) -> None:
        """SUPEX_COLOR should take priority over NO_COLOR."""
        with patch.dict(os.environ, {"SUPEX_COLOR": "1", "NO_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            assert _should_use_plain_output() is False

    def test_tty_detection_fallback(self) -> None:
        """Without env vars, should fall back to TTY detection."""
        with patch.dict(os.environ, {}, clear=True):
            from supex_driver.cli.output import _should_use_plain_output

            # Mock isatty to test both cases
            with patch.object(sys.stdout, "isatty", return_value=True):
                assert _should_use_plain_output() is False

            with patch.object(sys.stdout, "isatty", return_value=False):
                assert _should_use_plain_output() is True


class TestStripMarkup:
    """Test Rich markup stripping."""

    def test_strip_color_tags(self) -> None:
        """Should strip color tags."""
        from supex_driver.cli.output import _strip_markup

        assert _strip_markup("[green]text[/green]") == "text"
        assert _strip_markup("[red]error[/red]") == "error"
        assert _strip_markup("[yellow]warning[/yellow]") == "warning"
        assert _strip_markup("[cyan]info[/cyan]") == "info"

    def test_strip_style_tags(self) -> None:
        """Should strip style tags."""
        from supex_driver.cli.output import _strip_markup

        assert _strip_markup("[dim]faint[/dim]") == "faint"
        assert _strip_markup("[bold]strong[/bold]") == "strong"

    def test_strip_nested_tags(self) -> None:
        """Should strip nested tags."""
        from supex_driver.cli.output import _strip_markup

        assert _strip_markup("[green][bold]text[/bold][/green]") == "text"

    def test_preserve_unicode(self) -> None:
        """Should preserve unicode characters like checkmarks."""
        from supex_driver.cli.output import _strip_markup

        assert _strip_markup("[green]\u2713[/green] Done") == "\u2713 Done"
        assert _strip_markup("[red]\u2717[/red] Failed") == "\u2717 Failed"

    def test_preserve_text_without_markup(self) -> None:
        """Should preserve text without markup."""
        from supex_driver.cli.output import _strip_markup

        assert _strip_markup("plain text") == "plain text"
        assert _strip_markup("text with [brackets]") == "text with "

    def test_strip_opening_tag_only(self) -> None:
        """Should strip opening tags."""
        from supex_driver.cli.output import _strip_markup

        assert _strip_markup("[green]text") == "text"


class TestOutputClass:
    """Test Output class methods."""

    def test_is_plain_property(self) -> None:
        """is_plain property should reflect the mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            assert out.is_plain is True

        with patch.dict(os.environ, {"SUPEX_COLOR": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            assert out.is_plain is False

    def test_print_plain_mode(self) -> None:
        """print() should strip markup in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            with patch("builtins.print") as mock_print:
                out.print("[green]hello[/green]")
                mock_print.assert_called_once_with("hello")

    def test_success_plain_mode(self) -> None:
        """success() should use [OK] prefix in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            with patch("builtins.print") as mock_print:
                out.success("Done")
                mock_print.assert_called_once_with("[OK] Done")

    def test_error_plain_mode(self) -> None:
        """error() should use [ERROR] prefix in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            with patch("builtins.print") as mock_print:
                out.error("Something failed")
                mock_print.assert_called_once_with("[ERROR] Something failed", file=sys.stderr)

    def test_warning_plain_mode(self) -> None:
        """warning() should use [WARN] prefix in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            with patch("builtins.print") as mock_print:
                out.warning("Be careful")
                mock_print.assert_called_once_with("[WARN] Be careful")

    def test_info_plain_mode(self) -> None:
        """info() should print plain text in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            with patch("builtins.print") as mock_print:
                out.info("Information")
                mock_print.assert_called_once_with("Information")

    def test_panel_plain_mode(self) -> None:
        """panel() should print bordered text in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            captured: list[str] = []
            with patch("builtins.print", side_effect=lambda *args, **kwargs: captured.append(args[0] if args else "")):
                out.panel("Content here", title="Title")

            assert "--- Title ---" in captured
            assert "Content here" in captured

    def test_table_plain_mode(self) -> None:
        """table() should print aligned key-value pairs in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            captured: list[str] = []
            with patch("builtins.print", side_effect=lambda *args, **kwargs: captured.append(args[0] if args else "")):
                out.table({"name": "Test", "count": 42}, title="Info")

            assert "Info:" in captured
            assert any("name" in line and "Test" in line for line in captured)
            assert any("count" in line and "42" in line for line in captured)

    def test_json_plain_mode(self) -> None:
        """json() should print indented JSON in plain mode."""
        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output

            out = Output()
            with patch("builtins.print") as mock_print:
                out.json({"key": "value"})
                call_args = mock_print.call_args[0][0]
                assert '"key"' in call_args
                assert '"value"' in call_args


class TestGetOutput:
    """Test get_output() singleton behavior."""

    def test_get_output_returns_output_instance(self) -> None:
        """get_output() should return an Output instance."""
        # Reset global state
        import supex_driver.cli.output as output_module

        output_module._output = None

        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import Output, get_output

            result = get_output()
            assert isinstance(result, Output)

    def test_get_output_returns_same_instance(self) -> None:
        """get_output() should return the same instance on subsequent calls."""
        # Reset global state
        import supex_driver.cli.output as output_module

        output_module._output = None

        with patch.dict(os.environ, {"SUPEX_PLAIN": "1"}, clear=True):
            from supex_driver.cli.output import get_output

            first = get_output()
            second = get_output()
            assert first is second
