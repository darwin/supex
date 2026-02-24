"""Shared test fixtures for Radar tests."""

import pytest


@pytest.fixture(autouse=True)
def _no_launch(monkeypatch, tmp_path):
    """Prevent the CLI from actually launching the ingest pipeline / TUI."""
    monkeypatch.setattr("radar.cli._do_watch", lambda *_a, **_kw: None)
    # Default-mode watch needs SUPEX_WORKSPACE; provide a temp dir so tests
    # don't depend on the developer's shell environment.
    monkeypatch.setenv("SUPEX_WORKSPACE", str(tmp_path))
