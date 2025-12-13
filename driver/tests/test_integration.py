"""Integration tests using mock runtime server."""

import pytest

from supex_driver.connection import SketchupConnection
from supex_driver.connection.exceptions import (
    SketchUpConnectionError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
)

from tests.helpers.mock_runtime import MockRuntimeServer


@pytest.fixture
def mock_server():
    """Create and start a mock runtime server."""
    server = MockRuntimeServer()
    server.set_response("hello", result={"success": True})
    server.start()
    yield server
    server.stop()


class TestIntegrationHello:
    """Test hello handshake with mock server."""

    def test_hello_handshake_success(self, mock_server: MockRuntimeServer) -> None:
        """Test successful hello handshake."""
        conn = SketchupConnection(host="127.0.0.1", port=mock_server.port)
        assert conn.connect() is True
        assert conn._identified is True
        conn.disconnect()

    def test_hello_records_request(self, mock_server: MockRuntimeServer) -> None:
        """Test that hello request is recorded."""
        conn = SketchupConnection(
            host="127.0.0.1", port=mock_server.port, agent="test-agent"
        )
        conn.connect()
        conn.disconnect()

        assert len(mock_server.requests) == 1
        hello_req = mock_server.requests[0]
        assert hello_req["method"] == "hello"
        assert hello_req["params"]["agent"] == "test-agent"


class TestIntegrationToolCall:
    """Test tool calls with mock server."""

    def test_tool_call_success(self, mock_server: MockRuntimeServer) -> None:
        """Test successful tool call."""
        mock_server.set_response("tools/call", result={"text": "Hello from mock"})

        conn = SketchupConnection(host="127.0.0.1", port=mock_server.port)
        result = conn.send_command("ping")

        assert result["text"] == "Hello from mock"
        conn.disconnect()

    def test_tool_call_with_params(self, mock_server: MockRuntimeServer) -> None:
        """Test tool call with parameters."""
        mock_server.set_response("tools/call", result={"success": True})

        conn = SketchupConnection(host="127.0.0.1", port=mock_server.port)
        result = conn.send_command("eval_ruby", {"code": "1 + 1"})

        assert result["success"] is True

        # Check the recorded request
        tool_call = mock_server.requests[-1]
        assert tool_call["method"] == "tools/call"
        assert tool_call["params"]["name"] == "eval_ruby"
        assert tool_call["params"]["arguments"]["code"] == "1 + 1"
        conn.disconnect()

    def test_remote_error(self, mock_server: MockRuntimeServer) -> None:
        """Test remote error handling."""
        mock_server.set_response(
            "tools/call",
            error={"code": -32000, "message": "Ruby error: undefined method"},
        )

        conn = SketchupConnection(host="127.0.0.1", port=mock_server.port)

        with pytest.raises(SketchUpRemoteError) as exc_info:
            conn.send_command("bad_command")

        assert exc_info.value.code == -32000
        assert "Ruby error" in exc_info.value.message
        conn.disconnect()


class TestIntegrationTimeout:
    """Test timeout handling with mock server."""

    def test_timeout_on_slow_response(self, mock_server: MockRuntimeServer) -> None:
        """Test timeout when server responds slowly.

        Note: Timeout errors get wrapped in SketchUpConnectionError after retries.
        """
        mock_server.set_response("tools/call", result={"success": True})
        mock_server.set_delay(5.0, method="tools/call")  # Only delay tools/call

        conn = SketchupConnection(
            host="127.0.0.1", port=mock_server.port, timeout=0.2
        )

        # Timeout leads to connection error after retries
        with pytest.raises((SketchUpTimeoutError, SketchUpConnectionError)):
            conn.send_command("slow_command")

        conn.disconnect()


class TestIntegrationConnectionReuse:
    """Test connection reuse with mock server."""

    def test_multiple_commands_reuse_connection(
        self, mock_server: MockRuntimeServer
    ) -> None:
        """Test that multiple commands reuse the same connection."""
        mock_server.set_response("tools/call", result={"count": 1})

        conn = SketchupConnection(host="127.0.0.1", port=mock_server.port)

        # Send multiple commands
        for i in range(5):
            result = conn.send_command("get_count")
            assert "count" in result

        # Should have 1 hello + 5 tool calls = 6 requests
        # But they should all be on the same connection (1 hello)
        hello_count = sum(
            1 for r in mock_server.requests if r.get("method") == "hello"
        )
        assert hello_count == 1

        conn.disconnect()
