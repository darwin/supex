"""WebSocket relay between driver and VCAD viewer.

Runs a WebSocket server on localhost:9878 (configurable) that bridges
mesh data from the sidecar evaluation pipeline to the Tauri viewer
and exposes viewer state/screenshot to MCP tools.

Security: loopback-only (127.0.0.1), no authentication required.
The relay carries pre-computed mesh data, not source code or credentials.
"""

import asyncio
import base64
import contextlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("supex.vcad.viewer_relay")

# Configuration
VIEWER_RELAY_HOST = "127.0.0.1"
VIEWER_RELAY_PORT = int(os.environ.get("VCAD_VIEWER_RELAY_PORT", "9878"))

# Protocol
RELAY_PROTOCOL_VERSION = "1.0"
SUPPORTED_FEATURES = ["mesh", "screenshot", "state", "focus"]

# Screenshot constraints
SCREENSHOT_TIMEOUT = 10.0
MAX_INLINE_BASE64_BYTES = 128 * 1024  # 128 KB


def _parse_major_version(version: str) -> int:
    """Extract major version number from version string."""
    try:
        return int(version.split(".")[0])
    except (ValueError, IndexError):
        return -1


# --- Viewer-specific exceptions ---


class VCADViewerError(Exception):
    """Base exception for viewer relay errors."""


class VCADViewerNotConnectedError(VCADViewerError):
    """Raised when no viewer is connected."""


class VCADViewerTimeoutError(VCADViewerError):
    """Raised when a viewer operation times out."""


class VCADViewerProtocolError(VCADViewerError):
    """Raised on protocol mismatch."""

    def __init__(self, message: str, error_code: str = "PROTOCOL_MISMATCH") -> None:
        self.error_code = error_code
        self.details: dict[str, Any] = {}
        super().__init__(message)


class VCADViewerCapabilityError(VCADViewerError):
    """Raised when a required viewer capability is not available."""

    def __init__(
        self,
        required_capability: str,
        negotiated_capabilities: list[str],
        operation: str,
    ) -> None:
        self.required_capability = required_capability
        self.negotiated_capabilities = negotiated_capabilities
        self.operation = operation
        self.error_code = "CAPABILITY_UNAVAILABLE"
        self.details = {
            "required_capability": required_capability,
            "negotiated_capabilities": negotiated_capabilities,
            "operation": operation,
        }
        super().__init__(
            f"Capability '{required_capability}' not available for '{operation}'. "
            f"Negotiated: {negotiated_capabilities}"
        )


# --- Relay server ---


@dataclass
class VCADViewerSession:
    """State for a connected viewer."""

    protocol_version: str = ""
    features: list[str] = field(default_factory=list)
    negotiated: bool = False


class VCADViewerRelay:
    """WebSocket relay server for the VCAD viewer.

    Manages mesh push, viewer state, and screenshot relay between
    the driver (MCP tools + eval pipeline) and the Tauri viewer.

    The relay runs in a background thread with its own asyncio event loop.
    MCP tools interact via thread-safe methods.
    """

    def __init__(
        self,
        host: str = VIEWER_RELAY_HOST,
        port: int = VIEWER_RELAY_PORT,
        workspace: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.workspace = workspace or os.environ.get("SUPEX_WORKSPACE", ".")

        # Event loop + thread
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: Any = None
        self._started = threading.Event()

        # Connected viewer
        self._ws: Any = None  # websockets ServerConnection
        self._session = VCADViewerSession()
        self._lock = threading.Lock()

        # Viewer state (latest from viewer.state messages)
        self._viewer_state: dict[str, Any] | None = None

        # Applied mesh state (for snapshot on reconnect)
        self._applied_meshes: dict[str, dict[str, Any]] = {}
        self._applied_revisions: dict[str, int] = {}

        # Screenshot coordination
        self._screenshot_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}

        # Reconnect counter (for metrics)
        self.viewer_reconnect_total: int = 0

    @property
    def is_viewer_connected(self) -> bool:
        """Check if a viewer is currently connected and negotiated."""
        with self._lock:
            return self._ws is not None and self._session.negotiated

    @property
    def viewer_features(self) -> list[str]:
        """Get negotiated viewer features."""
        with self._lock:
            return list(self._session.features)

    @property
    def viewer_protocol_version(self) -> str | None:
        """Get viewer's protocol version."""
        with self._lock:
            return self._session.protocol_version if self._session.negotiated else None

    def start(self) -> None:
        """Start the WebSocket relay server in a background thread."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(
            target=self._run_loop,
            name="viewer-relay",
            daemon=True,
        )
        self._thread.start()
        self._started.wait(timeout=5.0)
        logger.info(f"Viewer relay started on ws://{self.host}:{self.port}")

    def stop(self) -> None:
        """Stop the WebSocket relay server."""
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._loop = None
        self._server = None
        logger.info("Viewer relay stopped")

    def _run_loop(self) -> None:
        """Run the asyncio event loop in the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"Viewer relay loop error: {e}")
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            self._loop.close()

    async def _serve(self) -> None:
        """Start the WebSocket server and run forever."""
        from websockets.asyncio.server import serve

        async with serve(
            self._handle_connection,
            self.host,
            self.port,
        ) as server:
            self._server = server
            self._started.set()
            await asyncio.Future()  # run forever (cancelled on loop.stop)

    async def _handle_connection(self, ws: Any) -> None:
        """Handle a viewer WebSocket connection."""
        remote = getattr(ws, "remote_address", "unknown")
        logger.info(f"Viewer connected from {remote}")

        # Close previous connection if any (outside lock to avoid holding
        # lock across await)
        old_ws = None
        with self._lock:
            old_ws = self._ws
            self._ws = ws
            self._session = VCADViewerSession()
            self._viewer_state = None

        if old_ws is not None:
            with contextlib.suppress(Exception):
                await old_ws.close()

        try:
            async for raw_message in ws:
                try:
                    msg = json.loads(raw_message)
                    await self._handle_message(ws, msg)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from viewer")
                except Exception as e:
                    logger.error(f"Error handling viewer message: {e}")
        except Exception as e:
            logger.info(f"Viewer disconnected: {e}")
        finally:
            with self._lock:
                if self._ws is ws:
                    self._ws = None
                    self._session = VCADViewerSession()
            logger.info("Viewer connection closed")

    async def _handle_message(self, ws: Any, msg: dict[str, Any]) -> None:
        """Process a message from the viewer."""
        msg_type = msg.get("type")

        if msg_type == "viewer.ready":
            await self._handle_viewer_ready(ws, msg)
        elif msg_type == "viewer.state":
            self._handle_viewer_state(msg)
        elif msg_type == "screenshot.response":
            self._handle_screenshot_response(msg)
        else:
            logger.debug(f"Unknown message type from viewer: {msg_type}")

    async def _handle_viewer_ready(self, ws: Any, msg: dict[str, Any]) -> None:
        """Handle viewer.ready -- protocol/capability negotiation."""
        viewer_version = msg.get("protocol_version", "0.0")
        viewer_features = msg.get("features", [])

        local_major = _parse_major_version(RELAY_PROTOCOL_VERSION)
        remote_major = _parse_major_version(viewer_version)

        if local_major != remote_major:
            logger.error(
                f"Protocol mismatch: driver={RELAY_PROTOCOL_VERSION}, "
                f"viewer={viewer_version}"
            )
            await ws.send(
                json.dumps(
                    {
                        "type": "error",
                        "code": "PROTOCOL_MISMATCH",
                        "message": (
                            f"Protocol version mismatch: "
                            f"driver={RELAY_PROTOCOL_VERSION}, viewer={viewer_version}"
                        ),
                        "details": {
                            "driver_version": RELAY_PROTOCOL_VERSION,
                            "viewer_version": viewer_version,
                        },
                    }
                )
            )
            await ws.close()
            return

        # Negotiate features (intersection of supported)
        negotiated = [f for f in viewer_features if f in SUPPORTED_FEATURES]

        with self._lock:
            self._session.protocol_version = viewer_version
            self._session.features = negotiated
            self._session.negotiated = True
            self.viewer_reconnect_total += 1

        # Emit to centralized metrics
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            get_vcad_metrics().increment("viewer_reconnect_total")
        except Exception:
            pass

        logger.info(
            f"Viewer negotiated: version={viewer_version}, features={negotiated}"
        )

        # Send scene snapshot with latest state
        await self._send_scene_snapshot(ws)

    def _handle_viewer_state(self, msg: dict[str, Any]) -> None:
        """Handle viewer.state -- update cached viewer state."""
        with self._lock:
            self._viewer_state = {
                "camera": msg.get("camera"),
                "selection": msg.get("selection"),
                "timestamp": time.time(),
            }

    def _handle_screenshot_response(self, msg: dict[str, Any]) -> None:
        """Handle screenshot.response -- resolve pending future."""
        request_id = msg.get("request_id")
        if not request_id or request_id not in self._screenshot_futures:
            logger.warning(f"Unexpected screenshot response: {request_id}")
            return

        future = self._screenshot_futures.pop(request_id)
        if not future.done():
            future.set_result(
                {
                    "data": msg.get("data", ""),
                    "width": msg.get("width", 0),
                    "height": msg.get("height", 0),
                }
            )

    async def _send_scene_snapshot(self, ws: Any) -> None:
        """Send scene.snapshot with latest mesh state after viewer.ready."""
        with self._lock:
            nodes = []
            for node_id, mesh_data in self._applied_meshes.items():
                revision = self._applied_revisions.get(node_id, 0)
                nodes.append(
                    {
                        **mesh_data,
                        "node_id": node_id,
                        "revision": revision,
                    }
                )

        await ws.send(json.dumps({"type": "scene.snapshot", "nodes": nodes}))

    # --- Public API (called from MCP tools / eval pipeline, thread-safe) ---

    def push_mesh_update(
        self,
        node_id: str,
        revision: int,
        positions: list[float],
        indices: list[int],
        normals: list[float],
        material: dict[str, Any],
        bbox: dict[str, Any] | None = None,
    ) -> None:
        """Push a mesh update to the viewer.

        Stores the mesh for snapshot replay and sends to connected viewer.
        Only publishes if revision is current (latest for this node).
        """
        with self._lock:
            current_rev = self._applied_revisions.get(node_id, 0)
            if revision < current_rev:
                logger.debug(
                    f"Skipping stale mesh push for {node_id}: "
                    f"rev={revision} < current={current_rev}"
                )
                return

            mesh_data: dict[str, Any] = {
                "positions": positions,
                "indices": indices,
                "normals": normals,
                "material": material,
                "bbox": bbox,
            }
            self._applied_meshes[node_id] = mesh_data
            self._applied_revisions[node_id] = revision
            ws = self._ws
            connected = self._session.negotiated

        if connected and ws is not None and self._loop is not None:
            msg = json.dumps(
                {
                    "type": "mesh.update",
                    "node_id": node_id,
                    "revision": revision,
                    **mesh_data,
                }
            )
            asyncio.run_coroutine_threadsafe(self._safe_send(ws, msg), self._loop)

    def push_mesh_remove(self, node_id: str) -> None:
        """Remove a mesh from the viewer."""
        with self._lock:
            self._applied_meshes.pop(node_id, None)
            self._applied_revisions.pop(node_id, None)
            ws = self._ws
            connected = self._session.negotiated

        if connected and ws is not None and self._loop is not None:
            msg = json.dumps({"type": "mesh.remove", "node_id": node_id})
            asyncio.run_coroutine_threadsafe(self._safe_send(ws, msg), self._loop)

    def push_scene_reset(self) -> None:
        """Reset the viewer scene (clear all meshes)."""
        with self._lock:
            self._applied_meshes.clear()
            self._applied_revisions.clear()
            ws = self._ws
            connected = self._session.negotiated

        if connected and ws is not None and self._loop is not None:
            msg = json.dumps({"type": "scene.reset"})
            asyncio.run_coroutine_threadsafe(self._safe_send(ws, msg), self._loop)

    def get_viewer_state(self) -> dict[str, Any] | None:
        """Get latest viewer state (camera, selection).

        Returns None if no viewer is connected or no state received.
        """
        with self._lock:
            if not self._session.negotiated:
                return None
            return dict(self._viewer_state) if self._viewer_state else None

    def get_applied_revisions(self) -> dict[str, int]:
        """Get the applied revision map (node_id -> revision)."""
        with self._lock:
            return dict(self._applied_revisions)

    def require_viewer(self, operation: str) -> None:
        """Assert viewer is connected and negotiated."""
        with self._lock:
            if self._ws is None:
                raise VCADViewerNotConnectedError(f"No viewer connected for {operation}")
            if not self._session.negotiated:
                raise VCADViewerProtocolError(
                    f"Viewer not negotiated for {operation}",
                    error_code="PROTOCOL_MISMATCH",
                )

    def require_feature(self, feature: str, operation: str) -> None:
        """Assert a viewer feature is available."""
        self.require_viewer(operation)
        with self._lock:
            if feature not in self._session.features:
                raise VCADViewerCapabilityError(
                    required_capability=feature,
                    negotiated_capabilities=list(self._session.features),
                    operation=operation,
                )

    def request_screenshot(self, timeout: float = SCREENSHOT_TIMEOUT) -> dict[str, Any]:
        """Request a screenshot from the viewer (blocking, thread-safe).

        Returns dict with 'data' (base64), 'width', 'height'.
        """
        self.require_feature("screenshot", "vcad_viewer_screenshot")

        if self._loop is None or self._loop.is_closed():
            raise VCADViewerNotConnectedError("Relay not running")

        async def _do_screenshot() -> dict[str, Any]:
            assert self._loop is not None
            request_id = str(uuid.uuid4())
            future: asyncio.Future[dict[str, Any]] = self._loop.create_future()
            self._screenshot_futures[request_id] = future

            with self._lock:
                ws = self._ws

            if ws is None:
                self._screenshot_futures.pop(request_id, None)
                raise VCADViewerNotConnectedError("No viewer connected")

            await ws.send(
                json.dumps({"type": "screenshot.request", "request_id": request_id})
            )

            try:
                return await asyncio.wait_for(future, timeout)
            except TimeoutError:
                self._screenshot_futures.pop(request_id, None)
                raise VCADViewerTimeoutError(f"Screenshot timeout after {timeout}s")

        concurrent_future = asyncio.run_coroutine_threadsafe(
            _do_screenshot(), self._loop
        )
        return concurrent_future.result(timeout=timeout + 1.0)

    def send_focus(self, node_id: str) -> None:
        """Send focus command to viewer."""
        self.require_feature("focus", "vcad_viewer_focus")

        with self._lock:
            ws = self._ws

        if ws is not None and self._loop is not None:
            msg = json.dumps({"type": "viewer.focus", "node_id": node_id})
            asyncio.run_coroutine_threadsafe(self._safe_send(ws, msg), self._loop)

    @staticmethod
    async def _safe_send(ws: Any, msg: str) -> None:
        """Send a message to a WebSocket, suppressing errors."""
        try:
            await ws.send(msg)
        except Exception as e:
            logger.debug(f"Failed to send to viewer: {e}")

    def save_screenshot(
        self,
        data_b64: str,
        width: int,
        height: int,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Save screenshot PNG to disk.

        Returns metadata dict with path, width, height, bytes, created_at.
        """
        if output_path:
            save_path = output_path
        else:
            screenshot_dir = os.path.join(self.workspace, ".tmp", "vcad-viewer")
            os.makedirs(screenshot_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            save_path = os.path.join(screenshot_dir, f"shot-{timestamp}.png")

        # Validate path is within workspace
        real_workspace = os.path.realpath(self.workspace)
        real_save = os.path.realpath(save_path)
        if (
            not real_save.startswith(real_workspace + os.sep)
            and real_save != real_workspace
        ):
            raise VCADViewerError(
                "PATH_NOT_ALLOWED: screenshot path must be within workspace"
            )

        png_bytes = base64.b64decode(data_b64)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, "wb") as f:
            f.write(png_bytes)

        metadata: dict[str, Any] = {
            "path": save_path,
            "width": width,
            "height": height,
            "bytes": len(png_bytes),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        # Include inline preview only for small payloads
        if len(data_b64) <= MAX_INLINE_BASE64_BYTES:
            metadata["inline_base64"] = data_b64

        return metadata


# Singleton relay instance
_relay_lock = threading.Lock()
_relay: VCADViewerRelay | None = None


def get_vcad_viewer_relay(
    workspace: str | None = None,
) -> VCADViewerRelay:
    """Get or create the singleton VCADViewerRelay instance.

    Starts the relay server on first call.
    """
    global _relay
    with _relay_lock:
        if _relay is None:
            _relay = VCADViewerRelay(workspace=workspace)
            _relay.start()
        return _relay
