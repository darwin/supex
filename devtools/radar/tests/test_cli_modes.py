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


class TestWatchLevelFilter:
    def test_level_flag_accepted(self):
        """--level ERROR is accepted and shown in output."""
        result = runner.invoke(app, ["watch", "--level", "ERROR"])
        assert result.exit_code == 0
        assert "level>=ERROR" in result.output

    def test_level_flag_case_insensitive(self):
        """--level error (lowercase) works."""
        result = runner.invoke(app, ["watch", "--level", "error"])
        assert result.exit_code == 0
        assert "level>=ERROR" in result.output

    def test_level_flag_short(self):
        """-l WARN works."""
        result = runner.invoke(app, ["watch", "-l", "WARN"])
        assert result.exit_code == 0
        assert "level>=WARN" in result.output

    def test_invalid_level_fails(self):
        """--level BOGUS exits with error."""
        result = runner.invoke(app, ["watch", "--level", "BOGUS"])
        assert result.exit_code == 1
        assert "unknown level" in result.output.lower() or "unknown level" in (result.stderr or "").lower()


class TestWatchSourceFilter:
    def test_source_flag_single(self):
        """--source cli-driver shows in output."""
        result = runner.invoke(app, ["watch", "--source", "cli-driver"])
        assert result.exit_code == 0
        assert "sources=cli-driver" in result.output

    def test_source_flag_repeated(self):
        """-s cli-driver -s mcp-stderr both appear."""
        result = runner.invoke(app, ["watch", "-s", "cli-driver", "-s", "mcp-stderr"])
        assert result.exit_code == 0
        assert "cli-driver" in result.output
        assert "mcp-stderr" in result.output

    def test_source_flag_comma_separated(self):
        """--source cli-driver,mcp-stderr comma-separated in one flag."""
        result = runner.invoke(app, ["watch", "--source", "cli-driver,mcp-stderr"])
        assert result.exit_code == 0
        assert "cli-driver" in result.output
        assert "mcp-stderr" in result.output

    def test_combined_level_and_source(self):
        """--level ERROR --source cli-driver both filters shown."""
        result = runner.invoke(app, ["watch", "--level", "ERROR", "--source", "cli-driver"])
        assert result.exit_code == 0
        assert "level>=ERROR" in result.output
        assert "sources=cli-driver" in result.output


class TestWatchCapacity:
    def test_capacity_flag(self):
        """--capacity 50000 is accepted."""
        result = runner.invoke(app, ["watch", "--capacity", "50000"])
        assert result.exit_code == 0
        assert "capacity=50000" in result.output

    def test_default_capacity(self):
        """Default capacity is 10000."""
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 0
        assert "capacity=10000" in result.output

    def test_capacity_too_small(self):
        """--capacity 10 fails (minimum is 100)."""
        result = runner.invoke(app, ["watch", "--capacity", "10"])
        assert result.exit_code != 0


class TestHelpOutput:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "radar" in result.output.lower()

    def test_watch_help(self):
        result = runner.invoke(app, ["watch", "--help"])
        assert result.exit_code == 0
        assert "watch" in result.output.lower()
        # Verify key options are documented
        assert "--level" in result.output
        assert "--source" in result.output
        assert "--capacity" in result.output
        assert "--plain" in result.output
        assert "--config" in result.output

    def test_parse_help(self):
        result = runner.invoke(app, ["parse", "--help"])
        assert result.exit_code == 0
        assert "parse" in result.output.lower()

    def test_main_help_has_examples(self):
        """Main help includes usage examples."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--plain" in result.output


class TestConfigGlobExpansion:
    def test_glob_path_in_config(self, tmp_path):
        """Config with glob path expands to matching files."""
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "a.log").touch()
        (logs / "b.log").touch()
        (logs / "c.txt").touch()  # should not match

        cfg = tmp_path / "radar.toml"
        cfg.write_text(
            f'workspace = "{logs}"\n\n'
            '[[source]]\nname = "test"\npath = "*.log"\nparser = "plain"\n'
        )
        # The config loads successfully (doesn't crash on glob expansion)
        from radar.cli import _load_config
        sources, overrides = _load_config(cfg)
        paths = [str(s.source_path) for s in sources]
        assert str(logs / "a.log") in paths
        assert str(logs / "b.log") in paths
        assert str(logs / "c.txt") not in paths


class TestAdHocDedup:
    def test_duplicate_files_deduplicated(self, tmp_path):
        """Duplicate ad-hoc files are deduplicated."""
        f = tmp_path / "test.log"
        f.touch()
        from radar.cli import _resolve_sources
        sources, _ = _resolve_sources("ad-hoc", [f, f], None)
        assert len(sources) == 1
