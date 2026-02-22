# Re-export su-mock fixtures for use in test files.
# Register custom markers

import pytest

from tests.fixtures.su_mock import su_mock, su_mock_process  # noqa: F401


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "su_mock: tests requiring the su-mock Ruby process"
    )


@pytest.fixture(autouse=True)
def _isolate_supex_state(tmp_path, monkeypatch):
    """Ensure no test writes .supex/ into the working directory.

    Sets SUPEX_WORKSPACE to a per-test temp directory and resets all
    global singletons that cache paths derived from it.
    """
    from supex_driver.connection.vcad_artifact_manifest import _reset_artifact_store
    from supex_driver.mcp.vcad_tools import _reset_vcad_dag

    monkeypatch.setenv("SUPEX_WORKSPACE", str(tmp_path))

    _reset_artifact_store()
    _reset_vcad_dag()
    yield
    _reset_artifact_store()
    _reset_vcad_dag()
