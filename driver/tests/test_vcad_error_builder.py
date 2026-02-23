"""Tests for centralized error envelope builder.

Covers:
- Builder unit checks: each mapped error_code validates required details keys
- Builder unit checks: missing details.operation is auto-filled from operation context
- Regression checks: no boundary path returns message-only error without structured details
- Regression checks: invalid internal payload normalizes to SCHEMA_VALIDATION_FAILED
- Snapshot checks: JSON error envelope shape is stable for representative errors
"""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from supex_driver.connection.vcad_exceptions import (
    ARTIFACT_READ_FAILED,
    CAPABILITY_UNAVAILABLE,
    PATH_NOT_ALLOWED,
    PROTOCOL_MISMATCH,
    SOURCE_FILE_MISSING,
    STATE_RECONCILE_REQUIRED,
    VCADCapabilityError,
    VCADConnectionError,
    VCADProtocolError,
    VCADRemoteError,
    VCADTimeoutError,
)
from supex_driver.connection.vcad_schema import (
    REQUIRED_ERROR_DETAILS,
    SCHEMA_VALIDATION_FAILED,
    build_error,
    clear_schema_cache,
)
from supex_driver.connection.vcad_viewer_relay import build_viewer_error
from supex_driver.mcp.vcad_tools import (
    _handle_sketchup_error,
    _handle_vcad_error,
    vcad_eval,
    vcad_place,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear schema cache before each test."""
    clear_schema_cache()
    yield
    clear_schema_cache()


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = MagicMock()
    ctx.request_id = "test-req-1"
    return ctx


@pytest.fixture
def mock_vcad():
    """Patch get_vcad_connection to return a mock VCADConnection."""
    with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get, \
         patch("builtins.open", mock_open(read_data="[cube 1.0 1.0 1.0]")):
        conn = MagicMock()
        mock_get.return_value = conn
        yield conn


# ===========================================================================
# Builder unit checks: each mapped error_code validates required details keys
# ===========================================================================


class TestBuilderValidatesRequiredKeys:
    """build_error() validates required details keys for each mapped error_code."""

    def test_protocol_mismatch_valid(self) -> None:
        """PROTOCOL_MISMATCH with all required keys passes validation."""
        result = build_error(
            PROTOCOL_MISMATCH,
            "Protocol version mismatch",
            {
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
            operation="vcad_eval",
        )
        assert result["error_code"] == PROTOCOL_MISMATCH
        assert result["details"]["expected_protocol"] == "1.0"
        assert result["details"]["actual_protocol"] == "2.0"
        assert result["details"]["operation"] == "vcad_eval"

    def test_capability_unavailable_valid(self) -> None:
        """CAPABILITY_UNAVAILABLE with all required keys passes validation."""
        result = build_error(
            CAPABILITY_UNAVAILABLE,
            "Capability missing",
            {
                "required_capability": "adt_cache",
                "negotiated_capabilities": ["eval", "inspect"],
                "operation": "vcad_place",
            },
        )
        assert result["error_code"] == CAPABILITY_UNAVAILABLE
        assert result["details"]["required_capability"] == "adt_cache"

    def test_path_not_allowed_valid(self) -> None:
        """PATH_NOT_ALLOWED with all required keys passes validation."""
        result = build_error(
            PATH_NOT_ALLOWED,
            "Path outside workspace",
            {"path": "/etc/passwd", "workspace": "/project"},
            operation="vcad_place:eval",
        )
        assert result["error_code"] == PATH_NOT_ALLOWED
        assert result["details"]["path"] == "/etc/passwd"
        assert result["details"]["workspace"] == "/project"
        assert result["details"]["operation"] == "vcad_place:eval"

    def test_source_file_missing_valid(self) -> None:
        """SOURCE_FILE_MISSING with all required keys passes validation."""
        result = build_error(
            SOURCE_FILE_MISSING,
            "Source file not found",
            {"node_id": "bracket", "source_file": "/project/bracket.cmp.oo"},
            operation="vcad_update:eval",
        )
        assert result["error_code"] == SOURCE_FILE_MISSING
        assert result["details"]["node_id"] == "bracket"

    def test_state_reconcile_required_valid(self) -> None:
        """STATE_RECONCILE_REQUIRED with all required keys passes validation."""
        result = build_error(
            STATE_RECONCILE_REQUIRED,
            "Reconciliation required",
            {"drift": "3 nodes diverged", "pending_nodes": ["bracket", "plate"]},
            operation="vcad_update",
        )
        assert result["error_code"] == STATE_RECONCILE_REQUIRED
        assert result["details"]["drift"] == "3 nodes diverged"

    def test_artifact_read_failed_valid(self) -> None:
        """ARTIFACT_READ_FAILED with all required keys passes validation."""
        result = build_error(
            ARTIFACT_READ_FAILED,
            "Failed to read manifest",
            {"manifest_path": "/project/.tmp/manifest.json", "reason": "Permission denied"},
            operation="vcad_update:eval",
        )
        assert result["error_code"] == ARTIFACT_READ_FAILED
        assert result["details"]["manifest_path"] == "/project/.tmp/manifest.json"

    def test_protocol_mismatch_missing_key_fails(self) -> None:
        """PROTOCOL_MISMATCH missing expected_protocol -> SCHEMA_VALIDATION_FAILED."""
        result = build_error(
            PROTOCOL_MISMATCH,
            "Protocol mismatch",
            {"actual_protocol": "2.0"},
            operation="vcad_eval",
        )
        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "expected_protocol" in result["details"]["missing_keys"]
        assert result["details"]["original_error_code"] == PROTOCOL_MISMATCH

    def test_source_file_missing_no_details_fails(self) -> None:
        """SOURCE_FILE_MISSING with no details -> SCHEMA_VALIDATION_FAILED."""
        result = build_error(
            SOURCE_FILE_MISSING,
            "Source file missing",
            operation="vcad_update",
        )
        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "node_id" in result["details"]["missing_keys"]
        assert "source_file" in result["details"]["missing_keys"]

    @pytest.mark.parametrize("error_code", list(REQUIRED_ERROR_DETAILS.keys()))
    def test_all_mapped_codes_reject_empty_details(self, error_code: str) -> None:
        """Every mapped error_code with empty details triggers SCHEMA_VALIDATION_FAILED."""
        result = build_error(error_code, "test error", operation="test_op")
        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert result["details"]["original_error_code"] == error_code


# ===========================================================================
# Builder unit checks: missing details.operation is auto-filled
# ===========================================================================


class TestBuilderAutoFillsOperation:
    """build_error() auto-fills missing details.operation from operation context."""

    def test_fills_missing_operation(self) -> None:
        """Missing details.operation is filled from operation parameter."""
        result = build_error(
            "NO_GEOMETRY",
            "Scene produced zero parts",
            {"node_id": "bracket"},
            operation="vcad_place:eval",
        )
        assert result["details"]["operation"] == "vcad_place:eval"

    def test_preserves_existing_operation(self) -> None:
        """Existing details.operation is not overwritten."""
        result = build_error(
            "NO_GEOMETRY",
            "Scene produced zero parts",
            {"operation": "original_op"},
            operation="vcad_eval",
        )
        assert result["details"]["operation"] == "original_op"

    def test_no_operation_no_details_key(self) -> None:
        """Without operation parameter, no operation key in details."""
        result = build_error("NO_GEOMETRY", "test", {"node_id": "n1"})
        assert "operation" not in result.get("details", {})

    def test_operation_creates_details(self) -> None:
        """Operation parameter creates details dict even when no details passed."""
        result = build_error("INTERNAL_ERROR", "test", operation="vcad_eval")
        assert result["details"]["operation"] == "vcad_eval"

    def test_does_not_mutate_input_details(self) -> None:
        """Builder does not mutate the input details dict."""
        original_details = {"node_id": "bracket"}
        build_error("NO_GEOMETRY", "test", original_details, operation="vcad_eval")
        assert "operation" not in original_details


# ===========================================================================
# Regression: no boundary path returns message-only error without details
# ===========================================================================


class TestNoBoundaryPathMessageOnly:
    """Every error path through MCP tools produces error_code + details."""

    def test_vcad_capability_error_has_structured_details(self, mock_ctx, mock_vcad) -> None:
        """VCADCapabilityError produces error_code + details."""
        mock_vcad.eval_with_imports.side_effect = VCADCapabilityError(
            required_capability="adt_cache",
            negotiated_capabilities=["eval"],
            operation="vcad_place",
        )
        result = json.loads(vcad_place(mock_ctx, node_id="n1", source_file="/f.cmp.oo"))
        assert result["error_code"] == CAPABILITY_UNAVAILABLE
        assert "details" in result
        assert result["details"]["required_capability"] == "adt_cache"

    def test_vcad_protocol_error_has_structured_details(self, mock_ctx, mock_vcad) -> None:
        """VCADProtocolError produces error_code + details."""
        mock_vcad.eval_with_imports.side_effect = VCADProtocolError(
            "Protocol mismatch",
            error_code=PROTOCOL_MISMATCH,
            details={"expected_protocol": "1.0", "actual_protocol": "2.0"},
        )
        result = json.loads(vcad_eval(mock_ctx, code="test"))
        assert result["error_code"] == PROTOCOL_MISMATCH
        assert "details" in result

    def test_vcad_remote_error_has_structured_details(self, mock_ctx, mock_vcad) -> None:
        """VCADRemoteError produces error_code + details."""
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000, message="NO_GEOMETRY", data={"node_id": "empty"}
        )
        result = json.loads(vcad_eval(mock_ctx, code="test"))
        assert "error_code" in result
        assert "details" in result

    def test_vcad_connection_error_has_structured_details(self, mock_ctx, mock_vcad) -> None:
        """VCADConnectionError produces error_code + details (not just error_type)."""
        mock_vcad.eval_with_imports.side_effect = VCADConnectionError("Connection refused")
        result = json.loads(vcad_eval(mock_ctx, code="test"))
        assert result["error_code"] == "CONNECTION_ERROR"
        assert "details" in result
        assert result["details"]["operation"] == "vcad_eval"

    def test_vcad_timeout_error_has_structured_details(self, mock_ctx, mock_vcad) -> None:
        """VCADTimeoutError produces error_code + details."""
        mock_vcad.eval_with_imports.side_effect = VCADTimeoutError("Timeout")
        result = json.loads(vcad_eval(mock_ctx, code="test"))
        assert result["error_code"] == "CONNECTION_ERROR"
        assert "details" in result

    def test_unexpected_error_has_structured_details(self, mock_ctx, mock_vcad) -> None:
        """Unexpected exception produces error_code + details."""
        mock_vcad.eval_with_imports.side_effect = RuntimeError("Something broke")
        result = json.loads(vcad_eval(mock_ctx, code="test"))
        assert result["error_code"] == "INTERNAL_ERROR"
        assert "details" in result
        assert result["details"]["operation"] == "vcad_eval"

    def test_handle_vcad_error_all_types_have_error_code(self) -> None:
        """Every exception type through _handle_vcad_error produces error_code."""
        exceptions = [
            VCADCapabilityError("eval", [], "op"),
            VCADProtocolError("mismatch"),
            VCADRemoteError(-32000, "error"),
            VCADConnectionError("refused"),
            VCADTimeoutError("timeout"),
            RuntimeError("unexpected"),
        ]
        for exc in exceptions:
            result = json.loads(_handle_vcad_error(exc, "test_op"))
            assert "error_code" in result, f"{type(exc).__name__} missing error_code"
            assert "details" in result or result.get("error_code") in (
                SCHEMA_VALIDATION_FAILED,
            ), f"{type(exc).__name__} missing details"

    def test_handle_sketchup_error_all_types_have_error_code(self) -> None:
        """Every exception type through _handle_sketchup_error produces error_code."""
        from supex_driver.connection.sketchup_exceptions import (
            SketchUpConnectionError,
            SketchUpProtocolError,
            SketchUpRemoteError,
            SketchUpTimeoutError,
        )

        exceptions: list[Exception] = [
            SketchUpRemoteError(-32000, "error"),
            SketchUpConnectionError("refused"),
            SketchUpTimeoutError("timeout"),
            SketchUpProtocolError("bad protocol"),
            RuntimeError("unexpected"),
        ]
        for exc in exceptions:
            result = json.loads(_handle_sketchup_error(exc, "test_op"))
            assert "error_code" in result, f"{type(exc).__name__} missing error_code"
            assert "details" in result, f"{type(exc).__name__} missing details"


# ===========================================================================
# Regression: invalid internal payload normalizes to SCHEMA_VALIDATION_FAILED
# ===========================================================================


class TestInvalidPayloadNormalization:
    """Invalid internal payloads normalize to SCHEMA_VALIDATION_FAILED."""

    def test_mapped_code_without_required_keys(self) -> None:
        """Mapped error_code with missing required keys -> SCHEMA_VALIDATION_FAILED."""
        result = build_error(
            PROTOCOL_MISMATCH,
            "Protocol mismatch",
        )
        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert result["details"]["original_error_code"] == PROTOCOL_MISMATCH

    def test_mapped_code_partial_keys(self) -> None:
        """Mapped error_code with partial keys -> SCHEMA_VALIDATION_FAILED."""
        result = build_error(
            PATH_NOT_ALLOWED,
            "Path outside workspace",
            {"path": "/etc/passwd"},
            operation="vcad_place",
        )
        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "workspace" in result["details"]["missing_keys"]

    def test_validation_failed_has_path_diagnostics(self) -> None:
        """SCHEMA_VALIDATION_FAILED includes path and expected diagnostics."""
        result = build_error(
            CAPABILITY_UNAVAILABLE,
            "missing cap",
            operation="test_op",
        )
        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert result["details"]["path"] == "$.details"
        assert "expected" in result["details"]
        assert "missing_keys" in result["details"]

    def test_unknown_code_no_validation(self) -> None:
        """Unknown error_code passes through without validation."""
        result = build_error(
            "CUSTOM_ERROR",
            "Something happened",
            {"custom_key": "value"},
            operation="test_op",
        )
        assert result["error_code"] == "CUSTOM_ERROR"
        assert result["details"]["custom_key"] == "value"

    def test_numeric_code_no_validation(self) -> None:
        """Numeric JSON-RPC error code passes through without validation."""
        result = build_error(-32000, "NO_GEOMETRY", {"node_id": "empty"}, operation="vcad_eval")
        assert result["error_code"] == -32000
        assert result["details"]["node_id"] == "empty"


# ===========================================================================
# Snapshot checks: JSON error envelope shape is stable
# ===========================================================================


class TestSnapshotEnvelopeShape:
    """JSON error envelope shape is stable for representative errors."""

    def test_capability_error_shape(self) -> None:
        """CAPABILITY_UNAVAILABLE envelope has exact expected shape."""
        result = build_error(
            CAPABILITY_UNAVAILABLE,
            "Capability 'adt_cache' not available for operation 'vcad_place'",
            {
                "required_capability": "adt_cache",
                "negotiated_capabilities": ["eval", "inspect"],
                "operation": "vcad_place",
            },
        )
        assert result == {
            "success": False,
            "error": "Capability 'adt_cache' not available for operation 'vcad_place'",
            "error_code": "CAPABILITY_UNAVAILABLE",
            "details": {
                "required_capability": "adt_cache",
                "negotiated_capabilities": ["eval", "inspect"],
                "operation": "vcad_place",
            },
        }

    def test_connection_error_shape(self) -> None:
        """CONNECTION_ERROR envelope has exact expected shape."""
        result = build_error(
            "CONNECTION_ERROR",
            "Connection refused",
            {"error_type": "connection"},
            operation="vcad_eval",
        )
        assert result == {
            "success": False,
            "error": "Connection refused",
            "error_code": "CONNECTION_ERROR",
            "details": {
                "error_type": "connection",
                "operation": "vcad_eval",
            },
        }

    def test_internal_error_shape(self) -> None:
        """INTERNAL_ERROR envelope has exact expected shape."""
        result = build_error(
            "INTERNAL_ERROR",
            "Something broke",
            {"error_type": "unexpected"},
            operation="vcad_place:eval",
        )
        assert result == {
            "success": False,
            "error": "Something broke",
            "error_code": "INTERNAL_ERROR",
            "details": {
                "error_type": "unexpected",
                "operation": "vcad_place:eval",
            },
        }

    def test_schema_validation_failed_shape(self) -> None:
        """SCHEMA_VALIDATION_FAILED envelope has exact expected shape."""
        result = build_error(PROTOCOL_MISMATCH, "Protocol mismatch")
        assert result == {
            "success": False,
            "error": (
                "Error response for PROTOCOL_MISMATCH missing required details: "
                "expected_protocol, actual_protocol, operation"
            ),
            "error_code": "SCHEMA_VALIDATION_FAILED",
            "details": {
                "path": "$.details",
                "expected": (
                    "required keys for PROTOCOL_MISMATCH: "
                    "['expected_protocol', 'actual_protocol', 'operation']"
                ),
                "missing_keys": ["expected_protocol", "actual_protocol", "operation"],
                "original_error_code": "PROTOCOL_MISMATCH",
            },
        }

    def test_remote_error_shape_through_handler(self, mock_ctx, mock_vcad) -> None:
        """VCADRemoteError through _handle_vcad_error has stable shape."""
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000, message="Loon evaluation error: syntax error", data={"error_code": "LOON_ERROR"}
        )
        result = json.loads(vcad_eval(mock_ctx, code="[bad"))
        assert result == {
            "success": False,
            "error": "Loon evaluation error: syntax error",
            "error_code": -32000,
            "details": {
                "error_code": "LOON_ERROR",
                "operation": "vcad_eval",
            },
        }


# ===========================================================================
# Viewer relay builder
# ===========================================================================


class TestViewerRelayBuilder:
    """build_viewer_error() produces consistent viewer error messages."""

    def test_protocol_mismatch_shape(self) -> None:
        """PROTOCOL_MISMATCH viewer error has expected shape."""
        result = build_viewer_error(
            "PROTOCOL_MISMATCH",
            "Protocol version mismatch: driver=1.0, viewer=2.0",
            details={
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
            operation="viewer_handshake",
        )
        assert result == {
            "type": "error",
            "code": "PROTOCOL_MISMATCH",
            "message": "Protocol version mismatch: driver=1.0, viewer=2.0",
            "details": {
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
                "operation": "viewer_handshake",
            },
        }

    def test_auto_fills_operation(self) -> None:
        """Operation is auto-filled in viewer error details."""
        result = build_viewer_error(
            "CAPABILITY_UNAVAILABLE",
            "Feature not available",
            details={"required_capability": "screenshot"},
            operation="vcad_viewer_screenshot",
        )
        assert result["details"]["operation"] == "vcad_viewer_screenshot"

    def test_preserves_existing_operation(self) -> None:
        """Existing operation in details is not overwritten."""
        result = build_viewer_error(
            "TEST_ERROR",
            "test",
            details={"operation": "original"},
            operation="override",
        )
        assert result["details"]["operation"] == "original"

    def test_no_details_no_operation(self) -> None:
        """Without details or operation, no details key in output."""
        result = build_viewer_error("SIMPLE_ERROR", "something broke")
        assert "details" not in result

    def test_does_not_mutate_input(self) -> None:
        """Builder does not mutate input details dict."""
        original = {"key": "value"}
        build_viewer_error("TEST", "test", details=original, operation="op")
        assert "operation" not in original
