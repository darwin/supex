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

import jsonschema

logger = logging.getLogger("supex.vcad.schema")

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"

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
    return schema


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


def clear_schema_cache() -> None:
    """Clear the schema cache (for testing)."""
    _schema_cache.clear()
