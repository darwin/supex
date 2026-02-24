"""Tests for SUPEX_WORKSPACE env var requirement in CLI."""

from typer.testing import CliRunner

from radar.cli import app

runner = CliRunner()


class TestResolveWorkspace:
    def test_default_mode_fails_without_workspace(self, monkeypatch):
        """Default mode exits with code 1 when SUPEX_WORKSPACE is unset."""
        monkeypatch.delenv("SUPEX_WORKSPACE", raising=False)
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 1

    def test_default_mode_uses_workspace_env(self, monkeypatch, tmp_path):
        """Default mode uses $SUPEX_WORKSPACE for log paths."""
        monkeypatch.setenv("SUPEX_WORKSPACE", str(tmp_path))
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 0
        assert str(tmp_path) in result.output

    def test_default_mode_shows_workspace_in_output(self, monkeypatch, tmp_path):
        """Output message includes the workspace path."""
        monkeypatch.setenv("SUPEX_WORKSPACE", str(tmp_path))
        result = runner.invoke(app, ["watch"])
        assert "default mode" in result.output
        assert str(tmp_path) in result.output

    def test_adhoc_mode_ignores_workspace(self, monkeypatch, tmp_path):
        """Ad-hoc mode works even without SUPEX_WORKSPACE."""
        monkeypatch.delenv("SUPEX_WORKSPACE", raising=False)
        f = tmp_path / "test.log"
        f.touch()
        result = runner.invoke(app, ["watch", str(f)])
        assert result.exit_code == 0
        assert "ad-hoc mode" in result.output

    def test_config_mode_ignores_workspace(self, monkeypatch, tmp_path):
        """Config mode works even without SUPEX_WORKSPACE."""
        monkeypatch.delenv("SUPEX_WORKSPACE", raising=False)
        cfg = tmp_path / "radar.toml"
        cfg.write_text('[project]\nname = "test"\n')
        result = runner.invoke(app, ["watch", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "config mode" in result.output
