"""Shared test fixtures for Radar tests."""

import pytest


@pytest.fixture(autouse=True)
def _no_launch(monkeypatch):
    """Prevent the CLI from actually launching the ingest pipeline / TUI."""
    monkeypatch.setattr("radar.cli._do_watch", lambda *_a, **_kw: None)
