"""SketchUp connection adapter via TCP sockets and JSON-RPC."""

import contextlib
import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from importlib.metadata import version as get_version
from typing import Any

from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
    SketchUpUnknownResultError,
)

logger = logging.getLogger("supex.connection")

# Configuration with environment variable support
DEFAULT_HOST = os.environ.get("SUPEX_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("SUPEX_PORT", "9876"))
DEFAULT_TIMEOUT = float(os.environ.get("SUPEX_TIMEOUT", "15.0"))
MAX_RETRIES = int(os.environ.get("SUPEX_RETRIES", "2"))
MAX_RESPONSE_BYTES = int(os.environ.get("SUPEX_MAX_RESPONSE", "10485760"))  # 10 MB default
MAX_IDLE_TIME = float(os.environ.get("SUPEX_IDLE_TIMEOUT", "300"))  # 5 min default
AUTH_TOKEN = os.environ.get("SUPEX_AUTH_TOKEN")

# Tools whose runtime handler only reads state. A request for one of these may be
# sent again after the connection dropped or timed out while waiting for the
# response. Every other tool mutates the model, the filesystem or the session,
# so a request whose outcome is unknown is never replayed automatically.
REPLAY_SAFE_TOOLS = frozenset({
    "ping",
    "console_capture_status",
    "get_model_info",
    "list_entities",
    "get_entity",
    "get_selection",
    "get_layers",
    "get_materials",
    "get_camera_info",
    "list_vcad_nodes",
    "get_vcad_node",
    "vcad.observer_poll",
    "resources/list",
})

# Tools that are not bound to the currently open model, so the expected-model
# guard (SUPEX_EXPECTED_MODEL / expected_model_path) is not injected for them.
# open_model is exempt because it is the way to reach the expected model.
MODEL_GUARD_EXEMPT_TOOLS = frozenset({
    "ping",
    "console_capture_status",
    "reload_extension",
    "open_model",
    "resources/list",
})

# Client identification
CLIENT_NAME = "supex-driver"
try:
    CLIENT_VERSION = get_version("supex-driver")
except Exception:
    CLIENT_VERSION = "0.0.0"

# Request ID counter (thread-safe)
_request_id_lock = threading.Lock()
_request_id_counter = 0


def _next_request_id() -> int:
    """Generate next request ID (thread-safe monotonic counter)."""
    global _request_id_counter
    with _request_id_lock:
        _request_id_counter += 1
        return _request_id_counter


def resolve_expected_model(
    value: str | None = None, workspace: str | None = None
) -> str | None:
    """Resolve the expected model path from an explicit value or SUPEX_EXPECTED_MODEL.

    Relative paths resolve against the workspace (SUPEX_WORKSPACE), falling back
    to the current directory. Returns an absolute, normalized path or None when
    no expected model is configured.
    """
    raw = value if value is not None else os.environ.get("SUPEX_EXPECTED_MODEL")
    if not raw:
        return None
    base = workspace or os.environ.get("SUPEX_WORKSPACE") or os.getcwd()
    return os.path.normpath(os.path.join(base, os.path.expanduser(raw)))


def _tool_name(method: str, params: dict[str, Any] | None) -> str:
    """Name of the runtime tool a send_command call addresses."""
    if method == "tools/call" and params and "name" in params:
        return str(params["name"])
    return method


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
    workspace: str | None = field(default_factory=lambda: os.environ.get("SUPEX_WORKSPACE"))
    expected_model: str | None = field(default_factory=resolve_expected_model)
    sock: socket.socket | None = field(default=None, repr=False)
    _identified: bool = field(default=False, repr=False)
    _last_activity: float = field(default=0.0, repr=False)
    _rpc_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

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

        # Add workspace if configured
        if self.workspace:
            hello_params["workspace"] = self.workspace

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

    def disconnect(self) -> None:
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

    def _is_connection_healthy(self) -> bool:
        """Check if existing connection is still valid.

        Returns:
            True if connection is healthy and can be reused, False otherwise.
        """
        if not self.sock or not self._identified:
            return False

        # Check idle timeout
        if self._last_activity > 0:
            idle_time = time.time() - self._last_activity
            if idle_time > MAX_IDLE_TIME:
                logger.debug(f"Connection idle for {idle_time:.1f}s, will reconnect")
                return False

        # Check if socket is still connected (non-blocking peek)
        try:
            self.sock.setblocking(False)
            try:
                data = self.sock.recv(1, socket.MSG_PEEK)
                if not data:
                    return False  # Connection closed by server
            except BlockingIOError:
                pass  # No data available = connection is alive
            finally:
                self.sock.setblocking(True)
                self.sock.settimeout(self.timeout)
            return True
        except Exception:
            return False

    def transport_info(self) -> dict[str, Any]:
        """Effective transport policy of this driver process.

        Reported by check_status so a session can verify what the running
        driver actually does (environment variables are read at import time).
        """
        return {
            "timeout_s": self.timeout,
            "max_retries": MAX_RETRIES,
            "replay_after_send": "read_only_tools_only",
            "expected_model": self.expected_model,
        }

    def _build_request(
        self, method: str, params: dict[str, Any] | None, request_id: Any
    ) -> dict[str, Any]:
        """Wrap a command into a JSON-RPC request, injecting the model guard."""
        if method == "tools/call" and params and "name" in params and "arguments" in params:
            name = str(params["name"])
            arguments = dict(params["arguments"] or {})
        elif method in ["resources/list"]:
            # Direct JSON-RPC methods that shouldn't be wrapped as tools
            return {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": request_id,
            }
        else:
            name = method
            arguments = dict(params or {})

        if (
            self.expected_model
            and name not in MODEL_GUARD_EXEMPT_TOOLS
            and "expected_model_path" not in arguments
        ):
            arguments["expected_model_path"] = self.expected_model

        return {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": request_id,
        }

    def send_command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: Any = None,
        replay_safe: bool | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to SketchUp and return the response.

        Failures before the request bytes reach the socket (connect, handshake,
        lock contention) are retried up to ``SUPEX_RETRIES`` times. Once the
        request has been sent, a timeout or dropped connection means SketchUp
        may still execute or may already have executed the request. Such a
        request is sent again only when it is replay-safe: read-only tools
        (``REPLAY_SAFE_TOOLS``) or an explicit ``replay_safe=True``. Otherwise
        ``SketchUpUnknownResultError`` is raised and the caller must inspect the
        model before repeating the operation.

        Args:
            method: The command/method name to invoke.
            params: Optional parameters for the command.
            request_id: Optional request ID for JSON-RPC.
            replay_safe: Override the replay policy for this call. ``None``
                derives it from the tool name.

        Returns:
            The result from the JSON-RPC response.

        Raises:
            SketchUpConnectionError: If connection fails or is lost before sending.
            SketchUpUnknownResultError: If the request was sent but no response arrived
                and the tool is not replay-safe.
            SketchUpProtocolError: If response is invalid JSON.
            SketchUpTimeoutError: If socket operation times out.
        """
        # Generate request_id if not provided
        if request_id is None:
            request_id = _next_request_id()

        tool = _tool_name(method, params)
        if replay_safe is None:
            replay_safe = tool in REPLAY_SAFE_TOOLS

        # Reuse existing connection if healthy
        if not self._is_connection_healthy() and not self.connect():
            raise SketchUpConnectionError("Not connected to SketchUp")
        if self.sock is None:
            raise SketchUpConnectionError("Socket not initialized after connect")

        request = self._build_request(method, params, request_id)
        request_bytes = json.dumps(request).encode("utf-8") + b"\n"

        # Retry logic for connection issues
        retry_count = 0

        while retry_count <= MAX_RETRIES:
            sent = False
            try:
                acquired = self._rpc_lock.acquire(timeout=self.timeout)
                if not acquired:
                    logger.warning(f"[req:{request_id}] RPC lock contention, timed out waiting")
                    raise SketchUpTimeoutError(
                        f"RPC lock contention: could not acquire lock within {self.timeout}s"
                    )

                try:
                    logger.debug(f"[req:{request_id}] Sending {tool}")

                    self.sock.sendall(request_bytes)
                    sent = True

                    response_data = self.receive_full_response(self.sock)
                    response = json.loads(response_data.decode("utf-8"))

                    logger.debug(f"[req:{request_id}] Response received")

                    # Validate response ID matches request
                    response_id = response.get("id")
                    if response_id != request_id:
                        logger.error(
                            f"[req:{request_id}] Response ID mismatch: "
                            f"expected={request_id}, got={response_id}"
                        )
                        self.disconnect()
                        raise SketchUpProtocolError(
                            f"Response ID mismatch: expected={request_id}, got={response_id}"
                        )

                    if "error" in response:
                        error = response["error"]
                        raise SketchUpRemoteError(
                            code=error.get("code", -1),
                            message=error.get("message", "Unknown error from SketchUp"),
                            data=error.get("data"),
                        )

                    # Update activity timestamp on success
                    self._last_activity = time.time()
                    result: dict[str, Any] = response.get("result", {})
                    return result
                finally:
                    self._rpc_lock.release()

            except (
                TimeoutError,
                ConnectionError,
                BrokenPipeError,
                ConnectionResetError,
                SketchUpTimeoutError,
                SketchUpConnectionError,
            ) as e:
                if sent and not replay_safe:
                    logger.error(
                        f"[req:{request_id}] {tool} was sent but no response arrived: {e}. "
                        "Not replaying a request with unknown outcome."
                    )
                    self.disconnect()
                    raise SketchUpUnknownResultError(
                        f"{tool} was sent to SketchUp but no response arrived within "
                        f"{self.timeout}s ({e}). SketchUp may still be executing it or may "
                        "have finished it; inspect the model before repeating the request."
                    ) from e

                logger.warning(
                    f"[req:{request_id}] Connection error (attempt {retry_count + 1}/{MAX_RETRIES + 1}): {e}"
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
                logger.error(f"[req:{request_id}] Invalid JSON response: {e}")
                if "response_data" in locals() and response_data:
                    logger.error(
                        f"[req:{request_id}] Raw response (first 200 bytes): {response_data[:200]!r}"
                    )
                raise SketchUpProtocolError(f"Invalid response from SketchUp: {e}")

            except Exception as e:
                logger.error(f"[req:{request_id}] Error: {e}")
                self.sock = None
                raise

        # If we get here, all retries were exhausted
        raise SketchUpConnectionError("Connection to SketchUp lost after all retries")


# Global connection management with thread safety
_connection_lock = threading.Lock()
_sketchup_connection: SketchupConnection | None = None
_connection_identity: tuple[str, str, int, str | None, str | None] | None = None  # (agent, host, port, workspace, expected_model)


def get_sketchup_connection(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, agent: str = "unknown"
) -> SketchupConnection:
    """Get or create a persistent SketchUp connection.

    Thread-safe singleton pattern for connection management.
    Cache key includes (agent, host, port, workspace, expected_model) — if any
    component changes, the old connection is disconnected and a new one is created.

    Args:
        host: Host to connect to.
        port: Port to connect to.
        agent: Agent identifier (e.g., "user", "Claude", "mcp").

    Returns:
        A SketchupConnection instance.
    """
    global _sketchup_connection, _connection_identity

    workspace = os.environ.get("SUPEX_WORKSPACE")
    expected_model = resolve_expected_model(workspace=workspace)
    new_identity = (agent, host, port, workspace, expected_model)

    with _connection_lock:
        # If identity changed (agent, host, port, or workspace), rotate connection
        if _sketchup_connection is not None and _connection_identity != new_identity:
            logger.info(
                f"Connection endpoint rotated: {_connection_identity} -> {new_identity}"
            )
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
            _sketchup_connection = SketchupConnection(
                host=host, port=port, agent=agent, workspace=workspace,
                expected_model=expected_model,
            )
            _connection_identity = new_identity
            # Note: Don't try to connect here - let individual commands handle connection attempts
            # This allows the server to remain available even when SketchUp isn't running
            logger.debug(f"Created SketchUp connection (agent: {agent}, will be established on first use)")

        return _sketchup_connection
