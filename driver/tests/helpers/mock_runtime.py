"""Mock SketchUp runtime server for integration testing."""

import contextlib
import json
import socket
import threading
import time
from typing import Any


class MockRuntimeServer:
    """Mock TCP server simulating SketchUp runtime.

    Usage:
        server = MockRuntimeServer()
        server.set_response('hello', result={'success': True})
        server.start()
        # ... run tests ...
        server.stop()
    """

    def __init__(self, port: int = 0):
        """Initialize mock server.

        Args:
            port: Port to bind to. 0 means auto-assign.
        """
        self.port = port
        self.server: socket.socket | None = None
        self.responses: dict[str, dict[str, Any]] = {}
        self.requests: list[dict[str, Any]] = []
        self.delay: float = 0.0
        self.delay_method: str | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the mock server."""
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", self.port))
        self.port = self.server.getsockname()[1]
        self.server.listen(5)
        self.server.settimeout(0.5)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the mock server."""
        self._running = False
        if self.server:
            with contextlib.suppress(Exception):
                self.server.close()
            self.server = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def set_response(
        self,
        method: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        """Set response for a method.

        Args:
            method: Method name (e.g., 'hello', 'tools/call')
            result: Result to return on success
            error: Error to return on failure
        """
        self.responses[method] = {"result": result, "error": error}

    def set_delay(self, delay: float, method: str | None = None) -> None:
        """Set response delay in seconds.

        Args:
            delay: Delay in seconds
            method: If specified, only delay this method (e.g., 'tools/call')
        """
        self.delay = delay
        self.delay_method = method

    def clear(self) -> None:
        """Clear recorded requests and reset delay."""
        self.requests = []
        self.delay = 0.0
        self.delay_method = None

    def _accept_loop(self) -> None:
        """Accept and handle connections."""
        while self._running:
            try:
                client, _ = self.server.accept()
                client.settimeout(5.0)
                threading.Thread(
                    target=self._handle_client, args=(client,), daemon=True
                ).start()
            except TimeoutError:
                continue
            except Exception:
                if self._running:
                    continue
                break

    def _handle_client(self, client: socket.socket) -> None:
        """Handle a single client connection."""
        try:
            while self._running:
                data = self._read_request(client)
                if not data:
                    break

                request = json.loads(data.decode("utf-8").strip())
                self.requests.append(request)

                # Apply delay before response (optionally only for specific method)
                method = request.get("method", "")
                if self.delay > 0 and (self.delay_method is None or method == self.delay_method):
                    time.sleep(self.delay)

                response = self._create_response(request)
                client.sendall(json.dumps(response).encode("utf-8") + b"\n")

        except Exception:
            pass
        finally:
            with contextlib.suppress(Exception):
                client.close()

    def _read_request(self, client: socket.socket) -> bytes | None:
        """Read a newline-delimited request."""
        data = bytearray()
        while True:
            try:
                chunk = client.recv(4096)
                if not chunk:
                    return None
                data.extend(chunk)
                if b"\n" in chunk:
                    return bytes(data)
            except TimeoutError:
                return None
            except Exception:
                return None

    def _create_response(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create response for a request."""
        method = request.get("method", "")
        request_id = request.get("id")

        # Check if we have a configured response
        if method in self.responses:
            resp_config = self.responses[method]
            if resp_config.get("error"):
                return {
                    "jsonrpc": "2.0",
                    "error": resp_config["error"],
                    "id": request_id,
                }
            return {
                "jsonrpc": "2.0",
                "result": resp_config.get("result", {}),
                "id": request_id,
            }

        # Default responses
        if method == "hello":
            return {
                "jsonrpc": "2.0",
                "result": {"success": True, "message": "Mock server"},
                "id": request_id,
            }
        if method == "ping":
            return {
                "jsonrpc": "2.0",
                "result": {"status": "ok"},
                "id": request_id,
            }

        # Unknown method
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": request_id,
        }
