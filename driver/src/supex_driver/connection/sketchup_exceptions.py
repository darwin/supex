"""Custom exceptions for SketchUp client communication."""

from typing import Any


class SketchUpError(Exception):
    """Base exception for SketchUp client errors."""

    pass


class SketchUpConnectionError(SketchUpError):
    """Raised when connection to SketchUp fails."""

    pass


class SketchUpTimeoutError(SketchUpError):
    """Raised when communication with SketchUp times out."""

    pass


class SketchUpProtocolError(SketchUpError):
    """Raised when there's a protocol error (invalid JSON, etc.)."""

    pass


class SketchUpRemoteError(SketchUpError):
    """Raised when SketchUp returns a JSON-RPC error response.

    Attributes:
        code: JSON-RPC error code from the response.
        message: Error message from SketchUp.
        data: Optional additional error data (may include file, line, hint).
    """

    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"[{code}] {message}")
