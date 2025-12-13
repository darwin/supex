"""SketchUp connection adapter via TCP sockets and JSON-RPC."""

import contextlib
import json
import logging
import os
import socket
import threading
from dataclasses import dataclass, field
from importlib.metadata import version as get_version
from typing import Any

from supex_driver.connection.exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
)

logger = logging.getLogger("supex.connection")

# Configuration with environment variable support
DEFAULT_HOST = os.environ.get("SUPEX_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("SUPEX_PORT", "9876"))
DEFAULT_TIMEOUT = float(os.environ.get("SUPEX_TIMEOUT", "15.0"))
MAX_RETRIES = int(os.environ.get("SUPEX_RETRIES", "2"))
MAX_RESPONSE_BYTES = int(os.environ.get("SUPEX_MAX_RESPONSE", "10485760"))  # 10 MB default
AUTH_TOKEN = os.environ.get("SUPEX_AUTH_TOKEN")

# Client identification
CLIENT_NAME = "supex-driver"
try:
    CLIENT_VERSION = get_version("supex-driver")
except Exception:
    CLIENT_VERSION = "0.0.0"


@dataclass
class SketchupConnection:
    """Connection adapter for SketchUp socket server.

    This class handles TCP socket communication with the SketchUp Ruby extension,
    using JSON-RPC 2.0 protocol for request/response.

    Example:
        >>> conn = SketchupConnection(agent="user")
        >>> result = conn.send_command("get_model_info")
        >>> print(result)
    """

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout: float = DEFAULT_TIMEOUT
    agent: str = "unknown"
    token: str | None = AUTH_TOKEN
    sock: socket.socket | None = field(default=None, repr=False)
    _identified: bool = field(default=False, repr=False)

    def connect(self) -> bool:
        """Connect to the SketchUp runtime socket server and send hello handshake.

        Returns:
            True if connection and identification successful, False otherwise.
        """
        # Always create fresh connections
        self.disconnect()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.connect((self.host, self.port))
            logger.debug(f"Created connection to SketchUp at {self.host}:{self.port}")

            # Send hello handshake
            if not self._send_hello():
                logger.error("Failed to identify with SketchUp server")
                self.disconnect()
                return False

            self._identified = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SketchUp: {e}")
            self.sock = None
            self._identified = False
            return False

    def _send_hello(self) -> bool:
        """Send hello handshake to identify this client.

        Returns:
            True if identification successful, False otherwise.
        """
        if not self.sock:
            return False

        hello_params = {
            "name": CLIENT_NAME,
            "version": CLIENT_VERSION,
            "agent": self.agent,
            "pid": os.getpid(),
        }

        # Add token if configured
        if self.token:
            hello_params["token"] = self.token

        hello_request = {
            "jsonrpc": "2.0",
            "method": "hello",
            "params": hello_params,
            "id": "hello",
        }

        try:
            request_bytes = json.dumps(hello_request).encode("utf-8") + b"\n"
            self.sock.sendall(request_bytes)

            response_data = self.receive_full_response(self.sock)
            response = json.loads(response_data.decode("utf-8"))

            if "error" in response:
                error_msg = response["error"].get("message", "Hello failed")
                logger.error(f"Hello handshake failed: {error_msg}")
                return False

            logger.debug(f"Hello handshake successful: {response.get('result', {})}")
            return True
        except Exception as e:
            logger.error(f"Hello handshake error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the SketchUp runtime."""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from SketchUp: {e}")
            finally:
                self.sock = None
                self._identified = False

    def receive_full_response(
        self, sock: socket.socket, buffer_size: int = 4096
    ) -> bytes:
        """Receive a complete newline-delimited JSON response.

        Reads from socket until a newline character is encountered,
        enforcing maximum response size limits.

        Args:
            sock: The socket to receive from.
            buffer_size: Size of receive buffer.

        Returns:
            Complete response as bytes (including trailing newline).

        Raises:
            SketchUpTimeoutError: If socket times out with no data.
            SketchUpConnectionError: If connection is lost.
            SketchUpProtocolError: If response exceeds size limit or is incomplete.
        """
        data = bytearray()
        sock.settimeout(self.timeout)

        try:
            while True:
                chunk = sock.recv(buffer_size)
                if not chunk:
                    if not data:
                        raise SketchUpConnectionError("Connection closed by server")
                    raise SketchUpProtocolError("Incomplete response: connection closed")

                data.extend(chunk)

                if len(data) > MAX_RESPONSE_BYTES:
                    raise SketchUpProtocolError(
                        f"Response exceeds maximum size ({MAX_RESPONSE_BYTES} bytes)"
                    )

                # Check if we have a complete message (newline-delimited)
                if b"\n" in chunk:
                    logger.debug(f"Received complete response ({len(data)} bytes)")
                    return bytes(data)

        except TimeoutError:
            if data:
                raise SketchUpProtocolError("Incomplete response: timeout with partial data")
            raise SketchUpTimeoutError(f"No response within {self.timeout}s")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            raise SketchUpConnectionError(f"Connection error: {e}")

    def send_command(
        self, method: str, params: dict[str, Any] | None = None, request_id: Any = None
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to SketchUp and return the response.

        Args:
            method: The command/method name to invoke.
            params: Optional parameters for the command.
            request_id: Optional request ID for JSON-RPC.

        Returns:
            The result from the JSON-RPC response.

        Raises:
            SketchUpConnectionError: If connection fails or is lost.
            SketchUpProtocolError: If response is invalid JSON.
            SketchUpTimeoutError: If socket operation times out.
        """
        if not self.connect():
            raise SketchUpConnectionError("Not connected to SketchUp")
        assert self.sock is not None  # connect() sets self.sock on success

        # Convert to proper JSON-RPC format
        if (
            method == "tools/call"
            and params
            and "name" in params
            and "arguments" in params
        ):
            # Already in correct format
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": request_id,
            }
        elif method in ["resources/list"]:
            # Direct JSON-RPC methods that shouldn't be wrapped as tools
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": request_id,
            }
        else:
            # Convert direct command to JSON-RPC tools/call format
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": method, "arguments": params or {}},
                "id": request_id,
            }

        # Retry logic for connection issues
        retry_count = 0

        while retry_count <= MAX_RETRIES:
            try:
                logger.debug(f"Sending JSON-RPC request: {request}")

                request_bytes = json.dumps(request).encode("utf-8") + b"\n"
                self.sock.sendall(request_bytes)

                response_data = self.receive_full_response(self.sock)
                response = json.loads(response_data.decode("utf-8"))

                logger.debug(f"Response parsed: {response}")

                if "error" in response:
                    error = response["error"]
                    raise SketchUpRemoteError(
                        code=error.get("code", -1),
                        message=error.get("message", "Unknown error from SketchUp"),
                        data=error.get("data"),
                    )

                return response.get("result", {})

            except (
                TimeoutError,
                ConnectionError,
                BrokenPipeError,
                ConnectionResetError,
                SketchUpTimeoutError,
                SketchUpConnectionError,
            ) as e:
                logger.warning(
                    f"Connection error (attempt {retry_count + 1}/{MAX_RETRIES + 1}): {e}"
                )
                retry_count += 1

                if retry_count <= MAX_RETRIES:
                    logger.info("Retrying connection...")
                    self.disconnect()
                    if not self.connect():
                        logger.error("Failed to reconnect")
                        break
                else:
                    logger.error("Max retries reached")
                    self.sock = None
                    raise SketchUpConnectionError(
                        f"Connection to SketchUp lost after {MAX_RETRIES + 1} attempts: {e}"
                    )

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from SketchUp: {e}")
                if "response_data" in locals() and response_data:
                    logger.error(
                        f"Raw response (first 200 bytes): {response_data[:200]!r}"
                    )
                raise SketchUpProtocolError(f"Invalid response from SketchUp: {e}")

            except Exception as e:
                logger.error(f"Error communicating with SketchUp: {e}")
                self.sock = None
                raise

        # If we get here, all retries were exhausted
        raise SketchUpConnectionError("Connection to SketchUp lost after all retries")


# Global connection management with thread safety
_connection_lock = threading.Lock()
_sketchup_connection: SketchupConnection | None = None
_connection_agent: str | None = None


def get_sketchup_connection(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, agent: str = "unknown"
) -> SketchupConnection:
    """Get or create a persistent SketchUp connection.

    Thread-safe singleton pattern for connection management.

    Args:
        host: Host to connect to.
        port: Port to connect to.
        agent: Agent identifier (e.g., "user", "Claude", "mcp").

    Returns:
        A SketchupConnection instance.
    """
    global _sketchup_connection, _connection_agent

    with _connection_lock:
        # If agent changed, recreate connection
        if _sketchup_connection is not None and _connection_agent != agent:
            logger.debug(f"Agent changed from {_connection_agent} to {agent}, recreating connection")
            with contextlib.suppress(Exception):
                _sketchup_connection.disconnect()
            _sketchup_connection = None

        if _sketchup_connection is not None:
            try:
                # Test connection health
                if _sketchup_connection.sock:
                    return _sketchup_connection
            except Exception as e:
                logger.warning(f"Existing connection is no longer valid: {e}")
                with contextlib.suppress(Exception):
                    _sketchup_connection.disconnect()
                _sketchup_connection = None

        if _sketchup_connection is None:
            _sketchup_connection = SketchupConnection(host=host, port=port, agent=agent)
            _connection_agent = agent
            # Note: Don't try to connect here - let individual commands handle connection attempts
            # This allows the server to remain available even when SketchUp isn't running
            logger.debug(f"Created SketchUp connection (agent: {agent}, will be established on first use)")

        return _sketchup_connection
