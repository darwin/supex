"""VCAD sidecar process lifecycle management."""

import logging
import os
import signal
import subprocess
import threading
import time

logger = logging.getLogger("supex.vcad.sidecar")

# Default sidecar binary path (relative to supex root)
_SIDECAR_RELATIVE_PATH = "vcad/sidecar/target/release/supex-vcad-sidecar"


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
        self.sidecar_path = sidecar_path or os.environ.get("VCAD_SIDECAR_PATH")
        self.process: subprocess.Popen | None = None
        self._lock = threading.Lock()

        # Resolve default path from supex root
        if not self.sidecar_path:
            root = _find_supex_root()
            if root:
                self.sidecar_path = os.path.join(root, _SIDECAR_RELATIVE_PATH)

    def ensure_running(self) -> None:
        """Start sidecar if not running. Check health via ping.

        If the sidecar process is already running and responsive, this is a no-op.
        If the process has exited or is unresponsive, it will be restarted.
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
        """Start the sidecar binary as a subprocess."""
        if not self.sidecar_path:
            logger.warning(
                "VCAD sidecar path not configured. "
                "Set VCAD_SIDECAR_PATH or build the sidecar binary."
            )
            return

        if not os.path.isfile(self.sidecar_path):
            logger.warning(f"VCAD sidecar binary not found at {self.sidecar_path}")
            return

        logger.info(f"Starting VCAD sidecar: {self.sidecar_path}")

        env = os.environ.copy()
        # Pass through VCAD-related env vars
        for key in (
            "VCAD_HOST",
            "VCAD_PORT",
            "VCAD_MAX_QUEUE",
            "VCAD_EVAL_TIMEOUT_MS",
            "VCAD_ADT_CACHE_MAX",
            "VCAD_ALLOW_REMOTE",
            "VCAD_TEMP_TTL_SEC",
            "VCAD_TEMP_MAX_FILES",
            "VCAD_AUTH_TOKEN",
            "VCAD_TEMP_DIR",
        ):
            if key in os.environ:
                env[key] = os.environ[key]

        # Default VCAD_TEMP_DIR to workspace .tmp/vcad-sidecar/ so OBJ files
        # are within SketchUp PathPolicy allowed roots
        if "VCAD_TEMP_DIR" not in env:
            workspace = os.environ.get("SUPEX_WORKSPACE")
            if workspace:
                temp_dir = os.path.join(workspace, ".tmp", "vcad-sidecar")
                os.makedirs(temp_dir, exist_ok=True)
                env["VCAD_TEMP_DIR"] = temp_dir

        try:
            self.process = subprocess.Popen(
                [self.sidecar_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Wait briefly for startup
            time.sleep(0.1)

            if self.process.poll() is not None:
                stdout = self.process.stdout.read() if self.process.stdout else b""
                stderr = self.process.stderr.read() if self.process.stderr else b""
                logger.error(
                    f"Sidecar exited immediately (code={self.process.returncode}). "
                    f"stderr: {stderr.decode('utf-8', errors='replace')[:500]}"
                )
                self._cleanup_process()
                return

            logger.info(f"VCAD sidecar started (pid={self.process.pid})")
        except FileNotFoundError:
            logger.error(f"VCAD sidecar binary not found: {self.sidecar_path}")
            self.process = None
        except PermissionError:
            logger.error(f"VCAD sidecar binary not executable: {self.sidecar_path}")
            self.process = None
        except Exception as e:
            logger.error(f"Failed to start VCAD sidecar: {e}")
            self.process = None

    def _cleanup_process(self) -> None:
        """Clean up process handles."""
        if self.process:
            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()
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
