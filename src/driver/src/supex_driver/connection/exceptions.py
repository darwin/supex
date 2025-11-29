"""Custom exceptions for SketchUp client communication."""


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
