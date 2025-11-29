"""SketchUp process management for e2e tests."""

import subprocess
import socket
import time
from pathlib import Path
from typing import Self


class SketchUpProcess:
    """Manages SketchUp process lifecycle for testing."""

    DEFAULT_PORT = 9876
    DEFAULT_HOST = "127.0.0.1"
    STARTUP_TIMEOUT = 60  # seconds
    POLL_INTERVAL = 0.5  # seconds

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        startup_timeout: float = STARTUP_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.startup_timeout = startup_timeout
        self._process: subprocess.Popen | None = None
        self._project_root = Path(__file__).parent.parent.parent

    @property
    def injector_script(self) -> Path:
        """Path to the Ruby injector script."""
        return self._project_root / "src" / "runtime" / "injector.rb"

    @property
    def template_path(self) -> Path:
        """Path to the test template file."""
        return self._project_root / "tests" / "data" / "template.skp"

    def start(self) -> None:
        """Start SketchUp and wait for it to be ready."""
        if self.is_running():
            return

        if not self.injector_script.exists():
            raise FileNotFoundError(f"Injector script not found: {self.injector_script}")

        if not self.template_path.exists():
            raise FileNotFoundError(f"Template file not found: {self.template_path}")

        # Launch SketchUp with Ruby injection and template
        args = [
            "open",
            "-a", "SketchUp",
            "--args",
            "-RubyStartup", str(self.injector_script),
            "-template", str(self.template_path),
        ]

        self._process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._project_root,
        )

        self.wait_for_ready()

    def wait_for_ready(self) -> None:
        """Wait until SketchUp is accepting connections."""
        start_time = time.time()
        while time.time() - start_time < self.startup_timeout:
            if self._check_port():
                return
            time.sleep(self.POLL_INTERVAL)

        raise TimeoutError(
            f"SketchUp did not become ready within {self.startup_timeout} seconds"
        )

    def _check_port(self) -> bool:
        """Check if the port is accepting connections."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                result = sock.connect_ex((self.host, self.port))
                return result == 0
        except OSError:
            return False

    def is_running(self) -> bool:
        """Check if SketchUp is running and accepting connections."""
        return self._check_port()

    def stop(self) -> None:
        """Stop SketchUp gracefully using AppleScript."""
        if not self.is_running():
            return

        try:
            subprocess.run(
                ["osascript", "-e", 'quit app "SketchUp"'],
                capture_output=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            self._force_kill()

        # Wait for process to actually stop
        self._wait_for_stop()

    def _force_kill(self) -> None:
        """Force kill SketchUp if graceful shutdown fails."""
        subprocess.run(
            ["pkill", "-9", "-f", "SketchUp"],
            capture_output=True,
        )

    def _wait_for_stop(self, timeout: float = 10.0) -> None:
        """Wait for SketchUp to stop."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_running():
                return
            time.sleep(0.5)

    def __enter__(self) -> Self:
        """Context manager entry - start SketchUp."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stop SketchUp."""
        self.stop()
