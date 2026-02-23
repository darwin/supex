"""Runtime schema validation for VCAD protocol payloads.

Validates incoming sidecar/viewer payloads and artifact manifests against
versioned JSON schemas from docs/contracts/v1/.

Validation failures produce SCHEMA_VALIDATION_FAILED error responses with
structured details (path, expected) for machine consumption.
"""

import json
import logging
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

logger = logging.getLogger("supex.vcad.schema")

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"

# Required details keys per error_code. At MCP boundary, all listed keys
# must be present in `details`; if any are missing the response is
# normalized to SCHEMA_VALIDATION_FAILED with path info.
REQUIRED_ERROR_DETAILS: dict[str, list[str]] = {
    "PROTOCOL_MISMATCH": ["expected_protocol", "actual_protocol", "operation"],
    "CAPABILITY_UNAVAILABLE": ["required_capability", "negotiated_capabilities", "operation"],
    "PATH_NOT_ALLOWED": ["path", "workspace", "operation"],
    "SOURCE_FILE_MISSING": ["node_id", "source_file", "operation"],
    "STATE_RECONCILE_REQUIRED": ["drift", "pending_nodes", "operation"],
    "ARTIFACT_READ_FAILED": ["manifest_path", "reason", "operation"],
}

# Resolve contracts directory relative to the repo root
_CONTRACTS_DIR = Path(__file__).resolve().parents[4] / "docs" / "contracts"

# Cache loaded schemas
_schema_cache: dict[str, dict[str, Any]] = {}


def _contracts_dir() -> Path:
    """Return the contracts directory path."""
    return _CONTRACTS_DIR


def load_schema(version: str, name: str) -> dict[str, Any]:
    """Load a JSON schema file from contracts directory.

    Args:
        version: Schema version directory (e.g. "v1").
        name: Schema file name without extension (e.g. "handshake").

    Returns:
        Parsed JSON schema dict.

    Raises:
        FileNotFoundError: If schema file does not exist.
    """
    cache_key = f"{version}/{name}"
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]

    schema_path = _contracts_dir() / version / f"{name}.schema.json"
    with open(schema_path) as f:
        schema = json.load(f)

    _schema_cache[cache_key] = schema
    return schema  # type: ignore[no-any-return]


def validate_payload(
    payload: dict[str, Any],
    version: str,
    schema_name: str,
    *,
    sub_schema: str | None = None,
) -> list[dict[str, str]]:
    """Validate a payload against a JSON schema.

    Args:
        payload: The data to validate.
        version: Schema version (e.g. "v1").
        schema_name: Schema file name without extension.
        sub_schema: Optional $defs key to validate against a specific
            sub-schema instead of the root schema.

    Returns:
        List of validation errors. Empty list means valid.
        Each error is a dict with 'path' and 'expected' keys.
    """
    try:
        schema = load_schema(version, schema_name)
    except FileNotFoundError:
        logger.warning(f"Schema not found: {version}/{schema_name}")
        return [{"path": "$", "expected": f"schema {version}/{schema_name} to exist"}]

    if sub_schema:
        defs = schema.get("$defs", {})
        if sub_schema not in defs:
            return [{"path": "$", "expected": f"sub-schema '{sub_schema}' in {schema_name}"}]
        # Build a wrapper schema that includes $defs so $ref can resolve
        target_schema = {**defs[sub_schema]}
        if "$defs" not in target_schema and defs:
            target_schema["$defs"] = defs
    else:
        target_schema = schema

    errors: list[dict[str, str]] = []
    validator = jsonschema.Draft202012Validator(
        target_schema,
        format_checker=jsonschema.FormatChecker(),
    )

    for error in validator.iter_errors(payload):
        path = ".".join(str(p) for p in error.absolute_path) or "$"
        expected = error.schema.get("description", error.message)
        errors.append({"path": path, "expected": expected})

    return errors


def make_validation_error_response(
    errors: list[dict[str, str]],
    message: str = "Payload validation failed",
) -> dict[str, Any]:
    """Create a standard error envelope for validation failures.

    Args:
        errors: Validation error list from validate_payload().
        message: Human-friendly error message.

    Returns:
        Error response dict matching error-envelope.schema.json.
    """
    first_error = errors[0] if errors else {}
    return {
        "success": False,
        "error": message,
        "error_code": SCHEMA_VALIDATION_FAILED,
        "details": {
            "path": first_error.get("path", "$"),
            "expected": first_error.get("expected", "unknown"),
            "validation_errors": errors,
        },
    }


def validate_handshake_response(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a sidecar hello response payload."""
    return validate_payload(payload, "v1", "handshake", sub_schema="hello_response")


def validate_handshake_request(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a hello request payload."""
    return validate_payload(payload, "v1", "handshake", sub_schema="hello_request")


def validate_viewer_relay(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a viewer relay message payload."""
    # Route to specific sub-schema based on message type
    msg_type = payload.get("type", "")
    type_to_schema = {
        "viewer.ready": "viewer_ready",
        "mesh.update": "mesh_update",
        "mesh.remove": "mesh_remove",
        "scene.reset": "scene_reset",
        "scene.snapshot": "scene_snapshot",
        "screenshot.request": "screenshot_request",
        "screenshot.response": "screenshot_response",
        "viewer.focus": "viewer_focus",
        "viewer.state": "viewer_state",
    }
    sub = type_to_schema.get(msg_type)
    if sub:
        return validate_payload(payload, "v1", "viewer-relay", sub_schema=sub)
    return validate_payload(payload, "v1", "viewer-relay")


def validate_artifact_manifest(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate an artifact manifest payload."""
    return validate_payload(payload, "v1", "artifact-manifest")


def validate_tools_call(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a tools/call input envelope."""
    return validate_payload(payload, "v1", "tools-call")


def validate_error_envelope(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate an error response envelope."""
    return validate_payload(payload, "v1", "error-envelope")


def build_error(
    code: str | int,
    message: str,
    details: dict[str, Any] | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    """Build a validated error envelope.

    Canonical error builder for all boundary layers. Ensures consistent
    error envelope shape with validated details for mapped error codes.

    Builder behavior:
    - Validates required details keys for mapped error codes
    - Auto-fills missing details.operation from operation context
    - Preserves upstream error_code when forwarding across boundaries
    - If required details are missing, converts to SCHEMA_VALIDATION_FAILED

    Args:
        code: Machine-readable error code (string or int for JSON-RPC codes).
        message: Human-readable error message.
        details: Structured error details dict.
        operation: Current operation name (auto-fills details.operation).

    Returns:
        Validated error envelope dict matching error-envelope.schema.json.
    """
    envelope: dict[str, Any] = {
        "success": False,
        "error": message,
        "error_code": code,
    }

    # Build details (copy to avoid mutating caller's dict)
    envelope_details = dict(details) if details is not None else {}

    # Auto-fill operation from context
    if operation and "operation" not in envelope_details:
        envelope_details["operation"] = operation

    # Always include details when non-empty
    if envelope_details:
        envelope["details"] = envelope_details

    # Validate required details for mapped error codes
    code_str = str(code)
    if code_str in REQUIRED_ERROR_DETAILS:
        required_keys = REQUIRED_ERROR_DETAILS[code_str]
        actual_details = envelope.get("details", {})
        missing = [k for k in required_keys if k not in actual_details]
        if missing:
            return {
                "success": False,
                "error": (
                    f"Error response for {code_str} missing required details: "
                    + ", ".join(missing)
                ),
                "error_code": SCHEMA_VALIDATION_FAILED,
                "details": {
                    "path": "$.details",
                    "expected": f"required keys for {code_str}: {required_keys}",
                    "missing_keys": missing,
                    "original_error_code": code_str,
                },
            }

    return envelope


def normalize_error_response(
    response: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    """Normalize an error response at the MCP boundary.

    Ensures that error responses with known error_code values carry all
    required details keys.  The driver never replaces the upstream
    error_code — it may only fill a missing ``details.operation``.

    If a required key is missing after enrichment, the response is
    replaced with a SCHEMA_VALIDATION_FAILED envelope listing the
    missing keys.

    Args:
        response: The error response dict (must have ``success=False``).
        operation: The MCP tool operation name (used to fill missing
            ``details.operation``).

    Returns:
        The (possibly enriched) response, or a SCHEMA_VALIDATION_FAILED
        response if required keys are absent.
    """
    error_code = response.get("error_code")
    if error_code is None or error_code not in REQUIRED_ERROR_DETAILS:
        return response

    required_keys = REQUIRED_ERROR_DETAILS[error_code]

    # Ensure details is a dict
    details = response.get("details")
    if details is None or not isinstance(details, dict):
        details = {}
        response["details"] = details

    # Fill missing operation (driver enrichment)
    if "operation" not in details:
        details["operation"] = operation

    # Validate all required keys are present
    missing = [k for k in required_keys if k not in details]
    if missing:
        return {
            "success": False,
            "error": (
                f"Error response for {error_code} missing required details: "
                + ", ".join(missing)
            ),
            "error_code": SCHEMA_VALIDATION_FAILED,
            "details": {
                "path": "$.details",
                "expected": f"required keys for {error_code}: {required_keys}",
                "missing_keys": missing,
                "original_error_code": error_code,
            },
        }

    return response


def clear_schema_cache() -> None:
    """Clear the schema cache (for testing)."""
    _schema_cache.clear()
