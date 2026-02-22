"""VCAD sidecar connection adapter via TCP sockets and JSON-RPC."""

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

from supex_driver.connection.vcad_exceptions import (
    CAPABILITY_UNAVAILABLE,
    PROTOCOL_MISMATCH,
    VCADCapabilityError,
    VCADConnectionError,
    VCADProtocolError,
    VCADRemoteError,
    VCADTimeoutError,
)

logger = logging.getLogger("supex.vcad.connection")

# Configuration with environment variable support
VCAD_HOST = os.environ.get("VCAD_HOST", "localhost")
VCAD_PORT = int(os.environ.get("VCAD_PORT", "9877"))
VCAD_TIMEOUT = float(os.environ.get("VCAD_TIMEOUT", "30.0"))
VCAD_MAX_RETRIES = int(os.environ.get("VCAD_RETRIES", "2"))
VCAD_MAX_RESPONSE_BYTES = int(os.environ.get("VCAD_MAX_RESPONSE", "10485760"))  # 10 MB
VCAD_MAX_IDLE_TIME = float(os.environ.get("VCAD_IDLE_TIMEOUT", "300"))  # 5 min
VCAD_AUTH_TOKEN = os.environ.get("VCAD_AUTH_TOKEN")

# Protocol version (major.minor)
PROTOCOL_VERSION = "1.0"

# Client identification
CLIENT_NAME = "supex-driver"
try:
    CLIENT_VERSION = get_version("supex-driver")
except Exception:
    CLIENT_VERSION = "0.0.0"

# Request ID counter (thread-safe)
_vcad_request_id_lock = threading.Lock()
_vcad_request_id_counter = 0


def _next_request_id() -> int:
    """Generate next request ID (thread-safe monotonic counter)."""
    global _vcad_request_id_counter
    with _vcad_request_id_lock:
        _vcad_request_id_counter += 1
        return _vcad_request_id_counter


def _parse_major_version(version) -> int:
    """Extract major version number from version string or int."""
    try:
        return int(str(version).split(".")[0])
    except (ValueError, IndexError):
        return -1


# Direct JSON-RPC methods (not wrapped as tools/call)
DIRECT_METHODS = {"hello", "ping", "resources/list"}


@dataclass
class VCADConnection:
    """TCP JSON-RPC 2.0 client for VCAD Rust sidecar.

    Mirrors SketchupConnection transport behavior with added protocol
    version negotiation and capability checking.

    Example:
        >>> conn = VCADConnection(agent="mcp")
        >>> result = conn.eval_code("[cube 10.0 10.0 10.0]")
    """

    host: str = VCAD_HOST
    port: int = VCAD_PORT
    timeout: float = VCAD_TIMEOUT
    agent: str = "unknown"
    token: str | None = VCAD_AUTH_TOKEN
    workspace: str | None = field(default_factory=lambda: os.environ.get("SUPEX_WORKSPACE"))
    sock: socket.socket | None = field(default=None, repr=False)
    _identified: bool = field(default=False, repr=False)
    _last_activity: float = field(default=0.0, repr=False)
    # Protocol negotiation state
    _protocol_version: str | None = field(default=None, repr=False)
    _capabilities: list[str] = field(default_factory=list, repr=False)
    _limits: dict[str, Any] = field(default_factory=dict, repr=False)

    def connect(self) -> bool:
        """Connect to the VCAD sidecar and perform protocol negotiation.

        Returns:
            True if connection and handshake successful, False otherwise.
        """
        self.disconnect()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.connect((self.host, self.port))
            logger.debug(f"Created connection to VCAD sidecar at {self.host}:{self.port}")

            if not self._send_hello():
                logger.error("Failed to identify with VCAD sidecar")
                self.disconnect()
                return False

            self._identified = True
            return True
        except VCADProtocolError:
            # Protocol mismatch is fail-fast — propagate immediately
            self.sock = None
            self._identified = False
            raise
        except Exception as e:
            logger.error(f"Failed to connect to VCAD sidecar: {e}")
            self.sock = None
            self._identified = False
            return False

    def _send_hello(self) -> bool:
        """Send hello handshake with protocol version negotiation.

        Returns:
            True if handshake and protocol negotiation successful.

        Raises:
            VCADProtocolError: On major protocol version mismatch (fail-fast).
        """
        if not self.sock:
            return False

        hello_params: dict[str, Any] = {
            "name": CLIENT_NAME,
            "version": CLIENT_VERSION,
            "agent": self.agent,
            "pid": os.getpid(),
            "protocol_version": PROTOCOL_VERSION,
        }

        if self.token:
            hello_params["token"] = self.token
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
                logger.error(f"VCAD hello handshake failed: {error_msg}")
                return False

            result = response.get("result", {})

            # Protocol version negotiation (fail-fast on major mismatch)
            sidecar_version = result.get("protocol_version", "0.0")
            local_major = _parse_major_version(PROTOCOL_VERSION)
            remote_major = _parse_major_version(sidecar_version)

            if local_major != remote_major:
                raise VCADProtocolError(
                    f"Protocol version mismatch: driver={PROTOCOL_VERSION}, "
                    f"sidecar={sidecar_version}",
                    error_code=PROTOCOL_MISMATCH,
                    details={
                        "driver_version": PROTOCOL_VERSION,
                        "sidecar_version": sidecar_version,
                    },
                )

            # Store negotiated capabilities and limits
            self._protocol_version = sidecar_version
            self._capabilities = result.get("capabilities", [])
            self._limits = result.get("limits", {})

            logger.debug(
                f"VCAD hello successful: version={sidecar_version}, "
                f"capabilities={self._capabilities}"
            )
            return True
        except VCADProtocolError:
            raise
        except Exception as e:
            logger.error(f"VCAD hello handshake error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the VCAD sidecar."""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from VCAD sidecar: {e}")
            finally:
                self.sock = None
                self._identified = False

    def receive_full_response(
        self, sock: socket.socket, buffer_size: int = 4096
    ) -> bytes:
        """Receive a complete newline-delimited JSON response.

        Args:
            sock: The socket to receive from.
            buffer_size: Size of receive buffer.

        Returns:
            Complete response as bytes.

        Raises:
            VCADTimeoutError: If socket times out with no data.
            VCADConnectionError: If connection is lost.
            VCADProtocolError: If response exceeds size limit or is incomplete.
        """
        data = bytearray()
        sock.settimeout(self.timeout)

        try:
            while True:
                chunk = sock.recv(buffer_size)
                if not chunk:
                    if not data:
                        raise VCADConnectionError("Connection closed by sidecar")
                    raise VCADProtocolError("Incomplete response: connection closed")

                data.extend(chunk)

                if len(data) > VCAD_MAX_RESPONSE_BYTES:
                    raise VCADProtocolError(
                        f"Response exceeds maximum size ({VCAD_MAX_RESPONSE_BYTES} bytes)"
                    )

                if b"\n" in chunk:
                    logger.debug(f"Received complete response ({len(data)} bytes)")
                    return bytes(data)

        except TimeoutError:
            if data:
                raise VCADProtocolError("Incomplete response: timeout with partial data")
            raise VCADTimeoutError(f"No response within {self.timeout}s")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            raise VCADConnectionError(f"Connection error: {e}")

    def _is_connection_healthy(self) -> bool:
        """Check if existing connection is still valid."""
        if not self.sock or not self._identified:
            return False

        if self._last_activity > 0:
            idle_time = time.time() - self._last_activity
            if idle_time > VCAD_MAX_IDLE_TIME:
                logger.debug(f"VCAD connection idle for {idle_time:.1f}s, will reconnect")
                return False

        try:
            self.sock.setblocking(False)
            try:
                data = self.sock.recv(1, socket.MSG_PEEK)
                if not data:
                    return False
            except BlockingIOError:
                pass
            finally:
                self.sock.setblocking(True)
                self.sock.settimeout(self.timeout)
            return True
        except Exception:
            return False

    def require_capability(self, capability: str, operation: str) -> None:
        """Assert that a capability was negotiated. Fail-fast if missing.

        Args:
            capability: Required capability name.
            operation: The operation requiring this capability.

        Raises:
            VCADCapabilityError: If capability was not negotiated.
        """
        if capability not in self._capabilities:
            raise VCADCapabilityError(
                required_capability=capability,
                negotiated_capabilities=list(self._capabilities),
                operation=operation,
            )

    def send_command(
        self, method: str, params: dict[str, Any] | None = None, request_id: Any = None
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to VCAD sidecar and return the response.

        Methods in DIRECT_METHODS (hello, ping, resources/list) are sent as
        direct JSON-RPC calls. All other methods are wrapped as tools/call
        with {"name": method, "arguments": params}.

        Args:
            method: The method name to invoke.
            params: Optional parameters for the method.
            request_id: Optional request ID.

        Returns:
            The result from the JSON-RPC response.

        Raises:
            VCADConnectionError: If connection fails.
            VCADProtocolError: If response is invalid.
            VCADTimeoutError: If operation times out.
            VCADRemoteError: If sidecar returns an error.
        """
        if request_id is None:
            request_id = _next_request_id()

        if not self._is_connection_healthy() and not self.connect():
            raise VCADConnectionError("Not connected to VCAD sidecar")
        if self.sock is None:
            raise VCADConnectionError("Socket not initialized after connect")

        # Build JSON-RPC request
        if (
            method == "tools/call"
            and params
            and "name" in params
            and "arguments" in params
        ):
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": request_id,
            }
        elif method in DIRECT_METHODS:
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": request_id,
            }
        else:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": method, "arguments": params or {}},
                "id": request_id,
            }

        retry_count = 0

        while retry_count <= VCAD_MAX_RETRIES:
            try:
                logger.debug(f"[req:{request_id}] Sending {method}")

                request_bytes = json.dumps(request).encode("utf-8") + b"\n"
                self.sock.sendall(request_bytes)

                response_data = self.receive_full_response(self.sock)
                response = json.loads(response_data.decode("utf-8"))

                logger.debug(f"[req:{request_id}] Response received")

                if "error" in response:
                    error = response["error"]
                    raise VCADRemoteError(
                        code=error.get("code", -1),
                        message=error.get("message", "Unknown error from VCAD sidecar"),
                        data=error.get("data"),
                    )

                self._last_activity = time.time()
                result: dict[str, Any] = response.get("result", {})
                return result

            except (
                TimeoutError,
                ConnectionError,
                BrokenPipeError,
                ConnectionResetError,
                VCADTimeoutError,
                VCADConnectionError,
            ) as e:
                logger.warning(
                    f"[req:{request_id}] Connection error "
                    f"(attempt {retry_count + 1}/{VCAD_MAX_RETRIES + 1}): {e}"
                )
                retry_count += 1

                if retry_count <= VCAD_MAX_RETRIES:
                    logger.info("Retrying VCAD connection...")
                    self.disconnect()
                    if not self.connect():
                        logger.error("Failed to reconnect to VCAD sidecar")
                        break
                else:
                    logger.error("Max retries reached for VCAD sidecar")
                    self.sock = None
                    raise VCADConnectionError(
                        f"Connection to VCAD sidecar lost after "
                        f"{VCAD_MAX_RETRIES + 1} attempts: {e}"
                    )

            except json.JSONDecodeError as e:
                logger.error(f"[req:{request_id}] Invalid JSON response: {e}")
                if "response_data" in locals() and response_data:
                    logger.error(
                        f"[req:{request_id}] Raw response (first 200 bytes): "
                        f"{response_data[:200]!r}"
                    )
                raise VCADProtocolError(f"Invalid response from VCAD sidecar: {e}")

            except Exception as e:
                logger.error(f"[req:{request_id}] Error: {e}")
                self.sock = None
                raise

        raise VCADConnectionError("Connection to VCAD sidecar lost after all retries")

    # Convenience methods for VCAD operations

    def eval_code(self, code: str) -> dict[str, Any]:
        """Evaluate Loon code and return the result.

        Args:
            code: Loon source code to evaluate.

        Returns:
            Evaluation result from sidecar.
        """
        return self.send_command("vcad.eval_code", {"code": code})

    def eval_file(self, path: str) -> dict[str, Any]:
        """Evaluate a Loon file and return the result.

        Args:
            path: Path to the .skp.oo file.

        Returns:
            Evaluation result from sidecar.
        """
        return self.send_command("vcad.eval_file", {"path": path})

    def inspect(self, code_or_path: str) -> dict[str, Any]:
        """Inspect Loon code or file without full evaluation.

        Args:
            code_or_path: Loon source code or file path to inspect.

        Returns:
            Inspection result from sidecar.
        """
        return self.send_command("vcad.inspect", {"code_or_path": code_or_path})

    def extract_imports(self, source: str) -> dict[str, Any]:
        """Parse source and extract import declarations.

        Args:
            source: Loon source code to scan for imports.

        Returns:
            Dict with 'imports' (list of import declarations) and
            'transformed_source' (source with imports replaced by symbols).
        """
        return self.send_command("vcad.extract_imports", {"source": source})

    def eval_with_imports(
        self,
        transformed_source: str,
        base_dir: str | None = None,
        imports: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate transformed source with resolved import data.

        Args:
            transformed_source: Source with import expressions replaced by symbols.
            base_dir: Optional base directory for module resolution.
            imports: Dict of import_id -> resolved import data.

        Returns:
            Evaluation result from sidecar.
        """
        params: dict[str, Any] = {
            "transformed_source": transformed_source,
        }
        if base_dir is not None:
            params["base_dir"] = base_dir
        if imports is not None:
            params["imports"] = imports
        return self.send_command("vcad.eval_with_imports", params)

    def watch_start(self, dir: str) -> dict[str, Any]:
        """Start watching a project directory for file changes.

        Args:
            dir: Absolute path to the project directory.

        Returns:
            Dict with 'status' and 'dir'.
        """
        return self.send_command("vcad.watch_start", {"dir": dir})

    def watch_stop(self) -> dict[str, Any]:
        """Stop the filesystem watcher.

        Returns:
            Dict with 'status'.
        """
        return self.send_command("vcad.watch_stop", {})

    def watch_poll(self) -> dict[str, Any]:
        """Poll for changed files since last poll.

        Returns:
            Dict with 'changes' list of {'path': str, 'kind': str}.
        """
        return self.send_command("vcad.watch_poll", {})

    def eval_with_solid_imports(
        self,
        transformed_source: str,
        base_dir: str | None = None,
        imports: dict[str, Any] | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate transformed source with data and solid imports.

        Solid imports reference cached ADT values in the sidecar's ADT cache.
        Data imports are injected as source-level let-bindings.

        Args:
            transformed_source: Source with import expressions replaced by symbols.
            base_dir: Optional base directory for module resolution.
            imports: Dict of import_id -> resolved import data (ResolvedImport format).
            node_id: Optional node ID to cache the result ADT under.

        Returns:
            Evaluation result from sidecar.
        """
        params: dict[str, Any] = {
            "transformed_source": transformed_source,
        }
        if base_dir is not None:
            params["base_dir"] = base_dir
        if imports is not None:
            params["imports"] = imports
        if node_id is not None:
            params["node_id"] = node_id
        return self.send_command("vcad.eval_with_solid_imports", params)


# Global connection management with thread safety
_vcad_connection_lock = threading.Lock()
_vcad_connection: VCADConnection | None = None
_vcad_connection_agent: str | None = None


def get_vcad_connection(
    host: str = VCAD_HOST,
    port: int = VCAD_PORT,
    agent: str = "unknown",
) -> VCADConnection:
    """Get or create a persistent VCAD sidecar connection.

    Thread-safe singleton pattern. On first call, ensures the sidecar
    process is running via VCADSidecar.ensure_running().

    Args:
        host: Host to connect to.
        port: Port to connect to.
        agent: Agent identifier.

    Returns:
        A VCADConnection instance.
    """
    global _vcad_connection, _vcad_connection_agent

    with _vcad_connection_lock:
        if _vcad_connection is not None and _vcad_connection_agent != agent:
            logger.debug(
                f"Agent changed from {_vcad_connection_agent} to {agent}, "
                "recreating VCAD connection"
            )
            with contextlib.suppress(Exception):
                _vcad_connection.disconnect()
            _vcad_connection = None

        if _vcad_connection is not None:
            try:
                if _vcad_connection.sock:
                    return _vcad_connection
            except Exception as e:
                logger.warning(f"Existing VCAD connection is no longer valid: {e}")
                with contextlib.suppress(Exception):
                    _vcad_connection.disconnect()
                _vcad_connection = None

        if _vcad_connection is None:
            # Auto-start sidecar before first connection
            from supex_driver.connection.vcad_sidecar import get_vcad_sidecar

            sidecar = get_vcad_sidecar()
            sidecar.ensure_running()

            _vcad_connection = VCADConnection(host=host, port=port, agent=agent)
            _vcad_connection_agent = agent
            logger.debug(
                f"Created VCAD connection (agent: {agent}, "
                "will be established on first use)"
            )

        return _vcad_connection
