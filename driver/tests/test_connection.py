"""Tests for SketchupConnection class."""

import json
import socket
from unittest.mock import Mock, patch

from supex_driver.connection import SketchupConnection


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
        from supex_driver.connection.connection import AUTH_TOKEN
        conn = SketchupConnection(host="localhost", port=9876)
        assert conn.token == AUTH_TOKEN
