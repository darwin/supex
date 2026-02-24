"""Tests for CLI mode selection and conflict handling."""

from typer.testing import CliRunner

from radar.cli import app

runner = CliRunner()


class TestWatchModeSelection:
    def test_default_mode(self):
        """radar watch with zero files runs in default mode."""
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 0
        assert "default mode" in result.output

    def test_adhoc_mode_single_file(self, tmp_path):
        """radar watch <file> enters ad-hoc mode."""
        f = tmp_path / "test.log"
        f.touch()
        result = runner.invoke(app, ["watch", str(f)])
        assert result.exit_code == 0
        assert "ad-hoc mode" in result.output

    def test_adhoc_mode_multiple_files(self, tmp_path):
        """radar watch <file1> <file2> enters ad-hoc mode."""
        f1 = tmp_path / "a.log"
        f2 = tmp_path / "b.log"
        f1.touch()
        f2.touch()
        result = runner.invoke(app, ["watch", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "ad-hoc mode" in result.output
        assert "2 file(s)" in result.output

    def test_config_mode(self, tmp_path):
        """radar watch --config <file> runs in config mode."""
        cfg = tmp_path / "radar.toml"
        cfg.write_text('[project]\nname = "test"\n')
        result = runner.invoke(app, ["watch", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "config mode" in result.output

    def test_adhoc_with_config_fails(self, tmp_path):
        """radar watch <file> --config <cfg> is a usage error."""
        f = tmp_path / "test.log"
        f.touch()
        cfg = tmp_path / "radar.toml"
        cfg.write_text('[project]\nname = "test"\n')
        result = runner.invoke(app, ["watch", str(f), "--config", str(cfg)])
        assert result.exit_code == 1
        assert "cannot combine" in result.output.lower() or "cannot combine" in (result.stderr or "")


class TestWatchPlainFlag:
    def test_plain_flag_default_mode(self):
        """--plain flag is accepted in default mode."""
        result = runner.invoke(app, ["watch", "--plain"])
        assert result.exit_code == 0
        assert "plain=True" in result.output

    def test_no_plain_flag(self):
        """Without --plain, plain is False."""
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 0
        assert "plain=False" in result.output


class TestHelpOutput:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "radar" in result.output.lower()

    def test_watch_help(self):
        result = runner.invoke(app, ["watch", "--help"])
        assert result.exit_code == 0
        assert "watch" in result.output.lower()

    def test_parse_help(self):
        result = runner.invoke(app, ["parse", "--help"])
        assert result.exit_code == 0
        assert "parse" in result.output.lower()
