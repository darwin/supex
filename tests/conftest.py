"""Pytest configuration and fixtures for e2e tests."""

import os
import tempfile
import time
from pathlib import Path

import pytest

from helpers.sketchup_process import SketchUpProcess
from helpers.cli_runner import CLIRunner


def get_project_temp_dir(subpath: str = "") -> Path:
    """Get path to project .tmp directory, creating subdirs if needed."""
    project_root = Path(__file__).parent.parent
    temp_dir = project_root / ".tmp" / subpath
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--no-sketchup-launch",
        action="store_true",
        default=False,
        help="Don't launch SketchUp (assume it's already running)",
    )
    parser.addoption(
        "--no-sketchup-stop",
        action="store_true",
        default=False,
        help="Don't stop SketchUp after tests",
    )


@pytest.fixture(scope="session")
def sketchup(request: pytest.FixtureRequest) -> SketchUpProcess:
    """
    Session-scoped fixture that manages SketchUp lifecycle.

    Starts SketchUp at the beginning of the test session and stops it at the end.
    Use --no-sketchup-launch to skip launching (useful when SketchUp is already running).
    Use --no-sketchup-stop to keep SketchUp running after tests.
    """
    no_launch = request.config.getoption("--no-sketchup-launch")
    no_stop = request.config.getoption("--no-sketchup-stop")

    process = SketchUpProcess()

    if not no_launch:
        process.start()

    yield process

    if not no_stop:
        # Save model to .tmp/tests/e2e/models before quitting to avoid save dialog
        # Reuses the same file created by test_model_file fixture
        try:
            temp_dir = get_project_temp_dir("tests/e2e/models")
            temp_file = temp_dir / "supex_test_session.skp"
            cli_runner = CLIRunner()
            cli_runner.save_model(str(temp_file))
        except Exception:
            # Ignore save errors during teardown
            pass

        process.stop()


@pytest.fixture(scope="session")
def cli(sketchup: SketchUpProcess) -> CLIRunner:
    """
    Session-scoped CLI runner.

    Depends on sketchup fixture to ensure SketchUp is running.
    Loads all Ruby snippets once at the start of the test session.
    """
    cli_runner = CLIRunner()
    # Load all snippet files once at session start
    result = cli_runner.load_snippets()
    if not result.success:
        raise RuntimeError(f"Failed to load snippets: {result.stderr}")
    return cli_runner


@pytest.fixture(scope="session")
def test_model_file(cli: CLIRunner) -> Path:
    """
    Session-scoped fixture that creates a single test model file.

    Saves the model once at the start of the test session to prevent
    save dialogs. This file is reused across all tests and by session teardown.
    """
    temp_dir = get_project_temp_dir("tests/e2e/models")
    temp_file = temp_dir / "supex_test_session.skp"
    cli.eval(f"Sketchup.active_model.save('{temp_file}')")
    return temp_file


@pytest.fixture
def fresh_model(cli: CLIRunner, test_model_file: Path) -> CLIRunner:
    """
    Function-scoped fixture that provides a clean model for each test.

    Clears the model to ensure clean state between tests. The model was
    already saved during session setup (test_model_file) to prevent save prompts.
    """
    # Clear the current model to ensure clean state
    cli.call_snippet('fixture_clear_all')

    return cli


@pytest.fixture
def populated_model(fresh_model: CLIRunner) -> CLIRunner:
    """
    Function-scoped fixture that provides a model with basic geometry.

    Creates a cube in the model for tests that need pre-existing geometry.
    """
    result = fresh_model.call_snippet('geom_create_cube')
    if not result.success:
        raise RuntimeError(f"Failed to create geometry: {result.stderr}")
    return fresh_model
