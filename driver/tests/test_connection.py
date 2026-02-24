"""Tests for SketchupConnection class."""

import json
import os
import socket
import threading
import time
from unittest.mock import Mock, patch

import pytest

from supex_driver.connection import SketchupConnection
from supex_driver.connection import sketchup_connection as connection_module
from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
)


class TestSketchupConnection:
    """Test the SketchupConnection class."""

    def test_connection_initialization(self) -> None:
        """Test SketchupConnection can be initialized."""
        conn = SketchupConnection(host="localhost", port=9876)
        assert conn.host == "localhost"
        assert conn.port == 9876
        assert conn.sock is None

    @patch("socket.socket")
    def test_connect_success(self, mock_socket: Mock) -> None:
        """Test successful connection to SketchUp with hello handshake."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Mock the hello response
        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {"success": True, "message": "Client identified"},
            "id": "hello"
        }).encode("utf-8") + b"\n"
        mock_sock_instance.recv.return_value = hello_response

        conn = SketchupConnection(host="localhost", port=9876, agent="test")
        result = conn.connect()

        assert result is True
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_sock_instance.connect.assert_called_once_with(("localhost", 9876))
        # Verify hello was sent
        mock_sock_instance.sendall.assert_called_once()
        sent_data = mock_sock_instance.sendall.call_args[0][0]
        sent_json = json.loads(sent_data.decode("utf-8").strip())
        assert sent_json["method"] == "hello"
        assert sent_json["params"]["agent"] == "test"
        assert conn.sock == mock_sock_instance
        assert conn._identified is True

    @patch("socket.socket")
    def test_connect_failure(self, mock_socket: Mock) -> None:
        """Test connection failure handling."""
        mock_socket.side_effect = ConnectionRefusedError("Connection refused")

        conn = SketchupConnection(host="localhost", port=9876)
        result = conn.connect()

        assert result is False
        assert conn.sock is None

    def test_disconnect(self) -> None:
        """Test disconnection from SketchUp."""
        mock_sock = Mock()
        conn = SketchupConnection(host="localhost", port=9876)
        conn.sock = mock_sock

        conn.disconnect()

        mock_sock.close.assert_called_once()
        assert conn.sock is None

    def test_disconnect_with_error(self) -> None:
        """Test disconnection handles socket errors gracefully."""
        mock_sock = Mock()
        mock_sock.close.side_effect = OSError("Socket error")

        conn = SketchupConnection(host="localhost", port=9876)
        conn.sock = mock_sock

        # Should not raise exception
        conn.disconnect()
        assert conn.sock is None


class TestJSONRPCFormat:
    """Test JSON-RPC request/response formatting."""

    def test_ping_request_format(self) -> None:
        """Test ping request format is valid JSON-RPC."""
        ping_request = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
            "id": 0,
        }

        # Should be valid JSON
        json_str = json.dumps(ping_request)
        parsed = json.loads(json_str)

        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "ping"
        assert parsed["id"] == 0

    def test_tools_call_format(self) -> None:
        """Test tools/call request format."""
        tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "create_component",
                "arguments": {
                    "type": "cube",
                    "position": [0, 0, 0],
                    "dimensions": [1, 1, 1],
                },
            },
            "id": 1,
        }

        # Should be valid JSON
        json_str = json.dumps(tools_request)
        parsed = json.loads(json_str)

        assert parsed["method"] == "tools/call"
        assert "name" in parsed["params"]
        assert "arguments" in parsed["params"]


class TestTokenAuthentication:
    """Test token authentication in hello handshake."""

    @patch("socket.socket")
    def test_hello_includes_token_when_set(self, mock_socket: Mock) -> None:
        """Test that hello includes token when token is configured."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Mock the hello response
        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {"success": True, "message": "Client identified"},
            "id": "hello"
        }).encode("utf-8") + b"\n"
        mock_sock_instance.recv.return_value = hello_response

        conn = SketchupConnection(host="localhost", port=9876, agent="test", token="test-secret")
        conn.connect()

        # Verify hello was sent with token
        mock_sock_instance.sendall.assert_called_once()
        sent_data = mock_sock_instance.sendall.call_args[0][0]
        sent_json = json.loads(sent_data.decode("utf-8").strip())
        assert sent_json["method"] == "hello"
        assert sent_json["params"]["token"] == "test-secret"

    @patch("socket.socket")
    def test_hello_without_token_when_not_set(self, mock_socket: Mock) -> None:
        """Test that hello does not include token when not configured."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Mock the hello response
        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {"success": True, "message": "Client identified"},
            "id": "hello"
        }).encode("utf-8") + b"\n"
        mock_sock_instance.recv.return_value = hello_response

        conn = SketchupConnection(host="localhost", port=9876, agent="test", token=None)
        conn.connect()

        # Verify hello was sent without token
        mock_sock_instance.sendall.assert_called_once()
        sent_data = mock_sock_instance.sendall.call_args[0][0]
        sent_json = json.loads(sent_data.decode("utf-8").strip())
        assert sent_json["method"] == "hello"
        assert "token" not in sent_json["params"]

    def test_token_field_defaults_to_env(self) -> None:
        """Test that token field uses AUTH_TOKEN constant by default."""
        from supex_driver.connection.sketchup_connection import AUTH_TOKEN
        conn = SketchupConnection(host="localhost", port=9876)
        assert conn.token == AUTH_TOKEN


class TestConnectionReuse:
    """Test connection reuse and health checking."""

    def test_is_connection_healthy_returns_false_when_no_socket(self) -> None:
        """Test health check returns False when socket is None."""
        conn = SketchupConnection(host="localhost", port=9876)
        assert conn._is_connection_healthy() is False

    def test_is_connection_healthy_returns_false_when_not_identified(self) -> None:
        """Test health check returns False when not identified."""
        conn = SketchupConnection(host="localhost", port=9876)
        conn.sock = Mock()
        conn._identified = False
        assert conn._is_connection_healthy() is False

    @patch("socket.socket")
    def test_connection_reuse_multiple_commands(self, mock_socket: Mock) -> None:
        """Test that multiple commands reuse the same connection."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Track request IDs from sendall to return matching response IDs
        sent_request_ids: list = []

        def sendall_side_effect(data):
            req = json.loads(data.decode("utf-8").strip())
            sent_request_ids.append(req.get("id"))

        mock_sock_instance.sendall.side_effect = sendall_side_effect

        def recv_side_effect(*args, **kwargs):
            # MSG_PEEK is used for health check - simulate no data available
            if args and args[0] == 1:
                raise BlockingIOError()
            req_id = sent_request_ids[-1]
            if req_id == "hello":
                return json.dumps({
                    "jsonrpc": "2.0",
                    "result": {"success": True},
                    "id": "hello"
                }).encode("utf-8") + b"\n"
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "ok"},
                "id": req_id
            }).encode("utf-8") + b"\n"

        mock_sock_instance.recv.side_effect = recv_side_effect

        conn = SketchupConnection(host="localhost", port=9876)

        # Send 3 commands
        for _ in range(3):
            conn.send_command("ping")

        # connect() should only be called once
        assert mock_sock_instance.connect.call_count == 1

    def test_health_check_detects_idle_timeout(self) -> None:
        """Test health check returns False when connection has been idle too long."""
        conn = SketchupConnection(host="localhost", port=9876)
        conn.sock = Mock()
        conn._identified = True

        # Set last activity to long ago
        conn._last_activity = time.time() - 1000

        # Temporarily set short idle timeout
        original_max_idle = connection_module.MAX_IDLE_TIME
        try:
            connection_module.MAX_IDLE_TIME = 1.0  # 1 second
            assert conn._is_connection_healthy() is False
        finally:
            connection_module.MAX_IDLE_TIME = original_max_idle

    def test_health_check_detects_closed_socket(self) -> None:
        """Test health check returns False when socket is closed by server."""
        conn = SketchupConnection(host="localhost", port=9876)
        mock_sock = Mock()
        conn.sock = mock_sock
        conn._identified = True
        conn._last_activity = time.time()

        # Mock recv returning empty bytes (connection closed)
        mock_sock.recv.return_value = b""

        assert conn._is_connection_healthy() is False

    def test_health_check_passes_when_no_data_available(self) -> None:
        """Test health check returns True when socket is alive but no data."""
        conn = SketchupConnection(host="localhost", port=9876)
        mock_sock = Mock()
        conn.sock = mock_sock
        conn._identified = True
        conn._last_activity = time.time()

        # Mock recv raising BlockingIOError (no data available)
        mock_sock.recv.side_effect = BlockingIOError()

        assert conn._is_connection_healthy() is True

    @patch("socket.socket")
    def test_reconnect_after_idle_timeout(self, mock_socket: Mock) -> None:
        """Test that connection reconnects after idle timeout."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Track request IDs from sendall to return matching response IDs
        sent_request_ids: list = []

        def sendall_side_effect(data):
            req = json.loads(data.decode("utf-8").strip())
            sent_request_ids.append(req.get("id"))

        mock_sock_instance.sendall.side_effect = sendall_side_effect

        def recv_side_effect(*args, **kwargs):
            # MSG_PEEK is used for health check - simulate no data available
            if args and args[0] == 1:
                raise BlockingIOError()
            req_id = sent_request_ids[-1]
            if req_id == "hello":
                return json.dumps({
                    "jsonrpc": "2.0",
                    "result": {"success": True},
                    "id": "hello"
                }).encode("utf-8") + b"\n"
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "ok"},
                "id": req_id
            }).encode("utf-8") + b"\n"

        mock_sock_instance.recv.side_effect = recv_side_effect

        conn = SketchupConnection(host="localhost", port=9876)

        # Send first command
        conn.send_command("ping")
        first_connect_count = mock_sock_instance.connect.call_count
        assert first_connect_count == 1

        # Simulate idle timeout by setting last_activity to old time
        original_max_idle = connection_module.MAX_IDLE_TIME
        try:
            connection_module.MAX_IDLE_TIME = 0.1
            conn._last_activity = time.time() - 1.0  # 1 second ago

            # Send second command - should trigger reconnect
            conn.send_command("ping")
            assert mock_sock_instance.connect.call_count == 2
        finally:
            connection_module.MAX_IDLE_TIME = original_max_idle

    @patch("socket.socket")
    def test_last_activity_updated_on_success(self, mock_socket: Mock) -> None:
        """Test that _last_activity is updated after successful command."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Track request IDs from sendall to return matching response IDs
        sent_request_ids: list = []

        def sendall_side_effect(data):
            req = json.loads(data.decode("utf-8").strip())
            sent_request_ids.append(req.get("id"))

        mock_sock_instance.sendall.side_effect = sendall_side_effect

        def recv_side_effect(*args, **kwargs):
            req_id = sent_request_ids[-1]
            if req_id == "hello":
                return json.dumps({
                    "jsonrpc": "2.0",
                    "result": {"success": True},
                    "id": "hello"
                }).encode("utf-8") + b"\n"
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "ok"},
                "id": req_id
            }).encode("utf-8") + b"\n"

        mock_sock_instance.recv.side_effect = recv_side_effect

        conn = SketchupConnection(host="localhost", port=9876)
        assert conn._last_activity == 0.0

        before = time.time()
        conn.send_command("ping")
        after = time.time()

        assert conn._last_activity >= before
        assert conn._last_activity <= after


class TestConnectionErrorHandling:
    """Test error handling in connection layer."""

    def test_send_command_raises_error_when_socket_is_none_after_connect(self) -> None:
        """Test that send_command raises proper error if socket is None after connect.

        This tests the safety check that replaces the previous assert statement,
        ensuring the code works correctly even with python -O.
        """
        conn = SketchupConnection(host="localhost", port=9876)

        # Mock connect to return True but leave sock as None (shouldn't happen normally)
        with (
            patch.object(conn, "connect", return_value=True),
            patch.object(conn, "_is_connection_healthy", return_value=False),
        ):
            conn.sock = None  # Ensure sock is None

            with pytest.raises(SketchUpConnectionError) as exc_info:
                conn.send_command("ping")

            assert "Socket not initialized" in str(exc_info.value)


class TestResponseIDValidation:
    """Test response ID matching in send_command."""

    @patch("socket.socket")
    def test_id_mismatch_raises_protocol_error(self, mock_socket: Mock) -> None:
        """Test that mismatched response ID raises ProtocolError and disconnects."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {"success": True},
            "id": "hello"
        }).encode("utf-8") + b"\n"

        # Response with wrong ID
        bad_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {"status": "ok"},
            "id": 999
        }).encode("utf-8") + b"\n"

        recv_responses = [hello_response, bad_response]
        mock_sock_instance.recv.side_effect = lambda *args, **kwargs: recv_responses.pop(0)

        conn = SketchupConnection(host="localhost", port=9876)

        with pytest.raises(SketchUpProtocolError, match="Response ID mismatch"):
            conn.send_command("ping")

    @patch("socket.socket")
    def test_matching_id_succeeds(self, mock_socket: Mock) -> None:
        """Test that matching response ID succeeds normally."""
        mock_sock_instance = Mock()
        mock_socket.return_value = mock_sock_instance

        # Track request IDs from sendall to return matching response IDs
        sent_request_ids: list = []

        def sendall_side_effect(data):
            req = json.loads(data.decode("utf-8").strip())
            sent_request_ids.append(req.get("id"))

        mock_sock_instance.sendall.side_effect = sendall_side_effect

        def recv_side_effect(*args, **kwargs):
            req_id = sent_request_ids[-1]
            if req_id == "hello":
                return json.dumps({
                    "jsonrpc": "2.0",
                    "result": {"success": True},
                    "id": "hello"
                }).encode("utf-8") + b"\n"
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {"status": "ok"},
                "id": req_id
            }).encode("utf-8") + b"\n"

        mock_sock_instance.recv.side_effect = recv_side_effect

        conn = SketchupConnection(host="localhost", port=9876)
        result = conn.send_command("ping")
        assert result == {"status": "ok"}


class TestRPCLockSerialization:
    """Test RPC lock serialization for concurrent access."""

    def test_connection_has_rpc_lock(self) -> None:
        """Test that SketchupConnection has an RPC lock."""
        conn = SketchupConnection(host="localhost", port=9876)
        assert hasattr(conn, "_rpc_lock")
        assert isinstance(conn._rpc_lock, type(threading.Lock()))


class TestSingletonRotation:
    """Test singleton connection rotation on endpoint change."""

    def setup_method(self) -> None:
        """Reset global singleton state before each test."""
        connection_module._sketchup_connection = None
        connection_module._connection_identity = None

    def teardown_method(self) -> None:
        """Clean up global singleton state after each test."""
        if connection_module._sketchup_connection is not None:
            connection_module._sketchup_connection.disconnect()
        connection_module._sketchup_connection = None
        connection_module._connection_identity = None

    def test_same_params_reuse_connection(self) -> None:
        """Test that same params return the same connection instance."""
        conn1 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="test"
        )
        conn2 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="test"
        )
        assert conn1 is conn2

    def test_different_port_rotates_connection(self) -> None:
        """Test that different port creates a new connection."""
        conn1 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="test"
        )
        conn2 = connection_module.get_sketchup_connection(
            host="localhost", port=9877, agent="test"
        )
        assert conn1 is not conn2
        assert conn2.port == 9877

    def test_different_host_rotates_connection(self) -> None:
        """Test that different host creates a new connection."""
        conn1 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="test"
        )
        conn2 = connection_module.get_sketchup_connection(
            host="192.168.1.1", port=9876, agent="test"
        )
        assert conn1 is not conn2
        assert conn2.host == "192.168.1.1"

    def test_different_agent_rotates_connection(self) -> None:
        """Test that different agent creates a new connection."""
        conn1 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="user"
        )
        conn2 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="mcp"
        )
        assert conn1 is not conn2
        assert conn2.agent == "mcp"

    @patch.dict(os.environ, {"SUPEX_WORKSPACE": "/project/a"})
    def test_different_workspace_rotates_connection(self) -> None:
        """Test that different workspace creates a new connection."""
        conn1 = connection_module.get_sketchup_connection(
            host="localhost", port=9876, agent="test"
        )
        with patch.dict(os.environ, {"SUPEX_WORKSPACE": "/project/b"}):
            conn2 = connection_module.get_sketchup_connection(
                host="localhost", port=9876, agent="test"
            )
        assert conn1 is not conn2

    def test_identity_includes_all_components(self) -> None:
        """Test that connection identity tracks all components."""
        connection_module.get_sketchup_connection(
            host="myhost", port=1234, agent="myagent"
        )
        identity = connection_module._connection_identity
        assert identity is not None
        assert identity[0] == "myagent"
        assert identity[1] == "myhost"
        assert identity[2] == 1234
