"""Custom assertion helpers for Supex tests.

These helpers provide more readable and consistent assertions for CLI results,
especially when dealing with JSON output from Ruby snippets.
"""

from typing import Any

from helpers.cli_runner import CLIResult


def assert_json_success(result: CLIResult, msg: str = "") -> dict[str, Any]:
    """Assert result is successful and return parsed JSON.

    Args:
        result: The CLI result to check.
        msg: Optional additional message for failure context.

    Returns:
        Parsed JSON data from stdout.

    Raises:
        AssertionError: If result is not successful or JSON parsing fails.
    """
    assert result.success, f"Command failed: {result.stderr}. {msg}"
    try:
        return result.json()
    except Exception as e:
        raise AssertionError(f"Failed to parse JSON from: {result.stdout}") from e


def assert_count(result: CLIResult, key: str, expected: int) -> None:
    """Assert a specific count in JSON result.

    Args:
        result: The CLI result to check.
        key: The key in JSON to check (e.g., "faces", "edges").
        expected: The expected count value.

    Raises:
        AssertionError: If count doesn't match expected.
    """
    data = assert_json_success(result)
    actual = data.get(key, data.get("count", 0))
    assert actual == expected, f"Expected {key}={expected}, got {actual}"


def assert_name(result: CLIResult, expected: str) -> None:
    """Assert the 'name' field in JSON result matches expected value.

    Args:
        result: The CLI result to check.
        expected: The expected name value.

    Raises:
        AssertionError: If name doesn't match expected.
    """
    data = assert_json_success(result)
    actual = data.get("name")
    assert actual == expected, f"Expected name='{expected}', got '{actual}'"


def assert_json_field(result: CLIResult, key: str, expected: Any) -> None:
    """Assert a specific field in JSON result matches expected value.

    Args:
        result: The CLI result to check.
        key: The key in JSON to check.
        expected: The expected value.

    Raises:
        AssertionError: If field value doesn't match expected.
    """
    data = assert_json_success(result)
    actual = data.get(key)
    assert actual == expected, f"Expected {key}={expected!r}, got {actual!r}"
