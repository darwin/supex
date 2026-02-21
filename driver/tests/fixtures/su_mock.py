"""
Pytest fixtures for su-mock headless SketchUp API test server.

Usage in tests:

    def test_something(su_mock):
        result = su_mock.send_command("ping")
        assert result["status"] == "connected"

The su_mock fixture provides a SketchupConnection with clean state per test.
"""

import os
import subprocess
import sys
import time

import pytest

# Default port for the mock server (avoid collision with real SketchUp)
SU_MOCK_PORT = int(os.environ.get("SUPEX_MOCK_PORT", "19876"))


@pytest.fixture(scope="session")
def su_mock_process():
    """Start su-mock Ruby process once per test session."""
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    mock_script = os.path.join(project_root, "mock", "src", "sketchup_mock.rb")

    if not os.path.exists(mock_script):
        pytest.skip("sketchup_mock.rb not found")

    proc = subprocess.Popen(
        ["ruby", mock_script, "--port", str(SU_MOCK_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=project_root,
    )

    # Wait for TCP ready
    import socket

    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", SU_MOCK_PORT), timeout=0.5)
            sock.close()
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode() if proc.stderr else ""
                pytest.fail(f"su-mock process exited early: {stderr}")
    else:
        proc.terminate()
        pytest.fail("su-mock did not become ready in time")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def su_mock(su_mock_process):
    """Per-test connection with clean state."""
    # Import here to avoid import errors when connection module is not available
    sys.path.insert(
        0,
        os.path.join(
            os.path.dirname(__file__), "..", "..", "src"
        ),
    )
    from supex_driver.connection.connection import SketchupConnection

    conn = SketchupConnection(port=SU_MOCK_PORT)

    # Reset mock state before each test
    conn.send_command("_test.reset")

    yield conn
