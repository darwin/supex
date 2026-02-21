"""Custom exceptions for vcad sidecar communication."""

from typing import Any


# Error codes (driver-local, transport/protocol level)
PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
SOURCE_FILE_MISSING = "SOURCE_FILE_MISSING"
STATE_RECONCILE_REQUIRED = "STATE_RECONCILE_REQUIRED"
NO_GEOMETRY = "NO_GEOMETRY"
MULTI_PART_UNSUPPORTED = "MULTI_PART_UNSUPPORTED"


class VcadError(Exception):
    """Base exception for vcad client errors."""


class VcadConnectionError(VcadError):
    """Raised when connection to vcad sidecar fails."""


class VcadTimeoutError(VcadError):
    """Raised when communication with vcad sidecar times out."""


class VcadProtocolError(VcadError):
    """Raised when there's a protocol error (invalid JSON, version mismatch, etc.).

    Attributes:
        error_code: Optional error code for structured error reporting.
        details: Optional additional details.
    """

    def __init__(
        self, message: str, error_code: str | None = None, details: dict[str, Any] | None = None
    ):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class VcadRemoteError(VcadError):
    """Raised when vcad sidecar returns a JSON-RPC error response.

    Preserves sidecar error_code unchanged for MCP tool responses.

    Attributes:
        code: JSON-RPC error code from the sidecar response.
        message: Error message from the sidecar.
        data: Optional additional error data.
    """

    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"[{code}] {message}")


class VcadCapabilityError(VcadError):
    """Raised when a required capability is not available after negotiation.

    Attributes:
        required_capability: The capability that was required.
        negotiated_capabilities: The capabilities that were negotiated.
        operation: The operation that required the capability.
        error_code: Always CAPABILITY_UNAVAILABLE.
    """

    def __init__(
        self,
        required_capability: str,
        negotiated_capabilities: list[str],
        operation: str,
    ):
        self.required_capability = required_capability
        self.negotiated_capabilities = negotiated_capabilities
        self.operation = operation
        self.error_code = CAPABILITY_UNAVAILABLE
        self.details = {
            "required_capability": required_capability,
            "negotiated_capabilities": negotiated_capabilities,
            "operation": operation,
        }
        super().__init__(
            f"Capability '{required_capability}' not available for operation '{operation}'. "
            f"Negotiated: {negotiated_capabilities}"
        )
