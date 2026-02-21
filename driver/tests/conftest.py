# Re-export su-mock fixtures for use in test files.
# Register custom markers

from tests.fixtures.su_mock import su_mock, su_mock_process  # noqa: F401


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "su_mock: tests requiring the su-mock Ruby process"
    )
