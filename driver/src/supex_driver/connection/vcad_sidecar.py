"""VCAD sidecar process lifecycle management."""

import json
import logging
import os
import signal
import socket
import subprocess
import threading
import time

logger = logging.getLogger("supex.vcad.sidecar")

# Default sidecar binary path (relative to supex root)
_SIDECAR_RELATIVE_PATH = "vcad/sidecar/target/release/supex-vcad-sidecar"

# Readiness probe configuration
_PROBE_RETRIES = 5
_PROBE_INTERVAL = 0.5  # seconds between retries


def _find_supex_root() -> str | None:
    """Find the supex project root directory."""
    # Walk up from this file's location
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isfile(os.path.join(current, "CLAUDE.md")) and os.path.isdir(
            os.path.join(current, "driver")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


class VCADSidecar:
    """Manages VCAD sidecar Rust binary process lifecycle.

    The sidecar is a Rust TCP server that evaluates Loon code and produces
    VCAD IR documents, BRep geometry, and meshes.

    The sidecar binary path defaults to
    ``<supex_root>/vcad/sidecar/target/release/supex-vcad-sidecar``
    and can be overridden with the ``VCAD_SIDECAR_PATH`` env var or
    constructor argument.
    """

    def __init__(self, sidecar_path: str | None = None):
        self.sidecar_path = sidecar_path or os.environ.get("SUPEX_VCAD_SIDECAR_PATH")
        self.process: subprocess.Popen | None = None
        self._lock = threading.Lock()

        # Resolve default path from supex root
        if not self.sidecar_path:
            root = _find_supex_root()
            if root:
                self.sidecar_path = os.path.join(root, _SIDECAR_RELATIVE_PATH)

    def ensure_running(self) -> None:
        """Start sidecar if not running. Verify readiness via TCP probe.

        If the sidecar process is already running and responsive, this is a no-op.
        If the process has exited or is unresponsive, it will be (re)started.
        """
        with self._lock:
            if self._is_alive():
                return

            if self.process is not None:
                logger.info("Sidecar process exited, cleaning up")
                self._cleanup_process()

            self._start()

    def stop(self) -> None:
        """Graceful shutdown via SIGTERM, with fallback to SIGKILL."""
        with self._lock:
            if self.process is None:
                return

            logger.info(f"Stopping VCAD sidecar (pid={self.process.pid})")
            try:
                self.process.send_signal(signal.SIGTERM)
                try:
                    self.process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    logger.warning("Sidecar did not exit after SIGTERM, sending SIGKILL")
                    self.process.kill()
                    self.process.wait(timeout=2.0)
            except (OSError, ProcessLookupError) as e:
                logger.debug(f"Error stopping sidecar: {e}")
            finally:
                self._cleanup_process()

    def _is_alive(self) -> bool:
        """Check if the sidecar process is still running."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def _start(self) -> None:
        """Start the sidecar binary as a subprocess and verify readiness."""
        if not self.sidecar_path:
            logger.warning(
                "VCAD sidecar path not configured. "
                "Set SUPEX_VCAD_SIDECAR_PATH or build the sidecar binary."
            )
            return

        if not os.path.isfile(self.sidecar_path):
            logger.warning(f"VCAD sidecar binary not found at {self.sidecar_path}")
            return

        logger.info(f"Starting VCAD sidecar: {self.sidecar_path}")

        env = os.environ.copy()
        # Pass through VCAD-related env vars
        for key in (
            "SUPEX_VCAD_HOST",
            "SUPEX_VCAD_PORT",
            "SUPEX_VCAD_MAX_QUEUE",
            "SUPEX_VCAD_EVAL_TIMEOUT_MS",
            "SUPEX_VCAD_ADT_CACHE_MAX",
            "SUPEX_VCAD_ALLOW_REMOTE",
            "SUPEX_VCAD_TEMP_TTL_SEC",
            "SUPEX_VCAD_TEMP_MAX_FILES",
            "SUPEX_VCAD_AUTH_TOKEN",
            "SUPEX_VCAD_TEMP_DIR",
        ):
            if key in os.environ:
                env[key] = os.environ[key]

        # Default SUPEX_VCAD_TEMP_DIR to workspace .tmp/vcad-sidecar/ so mesh files
        # are within SketchUp PathPolicy allowed roots
        if "SUPEX_VCAD_TEMP_DIR" not in env:
            workspace = os.environ.get("SUPEX_WORKSPACE")
            if workspace:
                temp_dir = os.path.join(workspace, ".tmp", "vcad-sidecar")
                os.makedirs(temp_dir, exist_ok=True)
                env["SUPEX_VCAD_TEMP_DIR"] = temp_dir

        host = env.get("SUPEX_VCAD_HOST", "localhost")
        port = int(env.get("SUPEX_VCAD_PORT", "9877"))

        try:
            self.process = subprocess.Popen(
                [self.sidecar_path],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=None,  # inherit parent stderr
            )

            # Readiness probe: TCP connect + ping with bounded retries
            if not self._wait_ready(host, port):
                # Process died during startup or started but unresponsive
                if self.process.poll() is not None:
                    logger.error(
                        f"Sidecar process died during startup "
                        f"(code={self.process.returncode})"
                    )
                else:
                    logger.error(
                        f"Sidecar started (pid={self.process.pid}) but unresponsive "
                        f"after {_PROBE_RETRIES} probes, killing"
                    )
                    self._force_kill()
                self._cleanup_process()
                return

            logger.info(f"VCAD sidecar ready (pid={self.process.pid})")
        except FileNotFoundError:
            logger.error(f"VCAD sidecar binary not found: {self.sidecar_path}")
            self.process = None
        except PermissionError:
            logger.error(f"VCAD sidecar binary not executable: {self.sidecar_path}")
            self.process = None
        except Exception as e:
            logger.error(f"Failed to start VCAD sidecar: {e}")
            self.process = None

    def _wait_ready(self, host: str, port: int) -> bool:
        """Probe sidecar with TCP connect + ping until ready or timeout.

        Returns True if sidecar responded to ping within retry budget.
        """
        for attempt in range(1, _PROBE_RETRIES + 1):
            # Check if process died
            if self.process is not None and self.process.poll() is not None:
                return False

            time.sleep(_PROBE_INTERVAL)

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((host, port))

                # Send a minimal ping request
                ping_req = json.dumps({
                    "jsonrpc": "2.0",
                    "method": "hello",
                    "params": {
                        "name": "supex-driver-probe",
                        "version": "0.0.0",
                        "protocol_version": "1.0",
                        "pid": os.getpid(),
                    },
                    "id": "probe",
                }).encode("utf-8") + b"\n"
                sock.sendall(ping_req)

                # Read response
                data = bytearray()
                while b"\n" not in data:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data.extend(chunk)

                sock.close()

                if data:
                    response = json.loads(data.decode("utf-8"))
                    if "result" in response:
                        logger.debug(
                            f"Readiness probe succeeded on attempt {attempt}"
                        )
                        return True

            except (ConnectionRefusedError, TimeoutError, OSError) as e:
                logger.debug(f"Readiness probe attempt {attempt}/{_PROBE_RETRIES}: {e}")
            except Exception as e:
                logger.debug(f"Readiness probe attempt {attempt}/{_PROBE_RETRIES}: {e}")

        return False

    def _force_kill(self) -> None:
        """Force-kill the sidecar process."""
        if self.process is None:
            return
        try:
            self.process.kill()
            self.process.wait(timeout=2.0)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            pass

    def _cleanup_process(self) -> None:
        """Clean up process handles."""
        if self.process:
            self.process = None


# Global sidecar singleton
_sidecar_lock = threading.Lock()
_sidecar: VCADSidecar | None = None


def get_vcad_sidecar(sidecar_path: str | None = None) -> VCADSidecar:
    """Get or create the global VCADSidecar instance.

    Args:
        sidecar_path: Optional path to sidecar binary.

    Returns:
        The VCADSidecar singleton.
    """
    global _sidecar

    with _sidecar_lock:
        if _sidecar is None:
            _sidecar = VCADSidecar(sidecar_path=sidecar_path)
        return _sidecar
