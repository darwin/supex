"""Tests for structured error details normalization.

Covers:
- Required-details checks: each mapped error_code returns all required details keys
- Message-only errors without required details fail normalization
- Passthrough checks: upstream error_code preserved unchanged through MCP boundary
- Driver enrichment limited to missing details.operation
- Negative checks: omitting one required detail key triggers SCHEMA_VALIDATION_FAILED
- Example fixture validation against updated error-envelope schema
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from supex_driver.connection.vcad_exceptions import (
    ARTIFACT_READ_FAILED,
    CAPABILITY_UNAVAILABLE,
    PATH_NOT_ALLOWED,
    PROTOCOL_MISMATCH,
    SOURCE_FILE_MISSING,
    STATE_RECONCILE_REQUIRED,
    VCADCapabilityError,
    VCADProtocolError,
    VCADRemoteError,
)
from supex_driver.connection.vcad_schema import (
    REQUIRED_ERROR_DETAILS,
    SCHEMA_VALIDATION_FAILED,
    clear_schema_cache,
    normalize_error_response,
    validate_error_envelope,
)
from supex_driver.mcp.vcad_tools import (
    _handle_vcad_error,
    vcad_eval,
    vcad_place,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES_DIR = _REPO_ROOT / "docs" / "contracts" / "examples"


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
    with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get:
        conn = MagicMock()
        mock_get.return_value = conn
        yield conn


def _load_example(name: str) -> dict[str, Any]:
    """Load a JSON example fixture by name."""
    path = _EXAMPLES_DIR / name
    with open(path) as f:
        return json.load(f)


# ===========================================================================
# Required-details checks: each mapped error_code returns all required keys
# ===========================================================================


class TestRequiredDetailsPresent:
    """Each mapped error_code returns all required details keys."""

    def test_protocol_mismatch_has_all_keys(self) -> None:
        """PROTOCOL_MISMATCH response includes expected_protocol, actual_protocol, operation."""
        response = {
            "success": False,
            "error": "Protocol version mismatch",
            "error_code": PROTOCOL_MISMATCH,
            "details": {
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
        }
        result = normalize_error_response(response, "vcad_eval")

        assert result["error_code"] == PROTOCOL_MISMATCH
        assert result["details"]["expected_protocol"] == "1.0"
        assert result["details"]["actual_protocol"] == "2.0"
        assert result["details"]["operation"] == "vcad_eval"

    def test_capability_unavailable_has_all_keys(self) -> None:
        """CAPABILITY_UNAVAILABLE includes required_capability, negotiated_capabilities, operation."""
        response = {
            "success": False,
            "error": "Capability missing",
            "error_code": CAPABILITY_UNAVAILABLE,
            "details": {
                "required_capability": "adt_cache",
                "negotiated_capabilities": ["eval", "inspect"],
                "operation": "vcad_place",
            },
        }
        result = normalize_error_response(response, "vcad_place")

        assert result["error_code"] == CAPABILITY_UNAVAILABLE
        assert result["details"]["required_capability"] == "adt_cache"
        assert result["details"]["negotiated_capabilities"] == ["eval", "inspect"]
        assert result["details"]["operation"] == "vcad_place"

    def test_path_not_allowed_has_all_keys(self) -> None:
        """PATH_NOT_ALLOWED includes path, workspace, operation."""
        response = {
            "success": False,
            "error": "Path outside workspace",
            "error_code": PATH_NOT_ALLOWED,
            "details": {
                "path": "/etc/passwd",
                "workspace": "/project",
                "operation": "vcad_place:eval",
            },
        }
        result = normalize_error_response(response, "vcad_place:eval")

        assert result["error_code"] == PATH_NOT_ALLOWED
        assert result["details"]["path"] == "/etc/passwd"
        assert result["details"]["workspace"] == "/project"
        assert result["details"]["operation"] == "vcad_place:eval"

    def test_source_file_missing_has_all_keys(self) -> None:
        """SOURCE_FILE_MISSING includes node_id, source_file, operation."""
        response = {
            "success": False,
            "error": "Source file not found",
            "error_code": SOURCE_FILE_MISSING,
            "details": {
                "node_id": "bracket",
                "source_file": "/project/bracket.skp.oo",
            },
        }
        result = normalize_error_response(response, "vcad_update:eval")

        assert result["error_code"] == SOURCE_FILE_MISSING
        assert result["details"]["node_id"] == "bracket"
        assert result["details"]["source_file"] == "/project/bracket.skp.oo"
        assert result["details"]["operation"] == "vcad_update:eval"

    def test_state_reconcile_required_has_all_keys(self) -> None:
        """STATE_RECONCILE_REQUIRED includes drift, pending_nodes, operation."""
        response = {
            "success": False,
            "error": "Reconciliation required",
            "error_code": STATE_RECONCILE_REQUIRED,
            "details": {
                "drift": "3 nodes diverged",
                "pending_nodes": ["bracket", "plate"],
            },
        }
        result = normalize_error_response(response, "vcad_update_cascade")

        assert result["error_code"] == STATE_RECONCILE_REQUIRED
        assert result["details"]["drift"] == "3 nodes diverged"
        assert result["details"]["pending_nodes"] == ["bracket", "plate"]
        assert result["details"]["operation"] == "vcad_update_cascade"

    def test_artifact_read_failed_has_all_keys(self) -> None:
        """ARTIFACT_READ_FAILED includes manifest_path, reason, operation."""
        response = {
            "success": False,
            "error": "Failed to read manifest",
            "error_code": ARTIFACT_READ_FAILED,
            "details": {
                "manifest_path": "/project/.tmp/manifest.json",
                "reason": "Permission denied",
            },
        }
        result = normalize_error_response(response, "vcad_update:eval")

        assert result["error_code"] == ARTIFACT_READ_FAILED
        assert result["details"]["manifest_path"] == "/project/.tmp/manifest.json"
        assert result["details"]["reason"] == "Permission denied"
        assert result["details"]["operation"] == "vcad_update:eval"

    def test_all_error_codes_covered(self) -> None:
        """REQUIRED_ERROR_DETAILS covers all 6 specified error codes."""
        expected_codes = {
            "PROTOCOL_MISMATCH",
            "CAPABILITY_UNAVAILABLE",
            "PATH_NOT_ALLOWED",
            "SOURCE_FILE_MISSING",
            "STATE_RECONCILE_REQUIRED",
            "ARTIFACT_READ_FAILED",
        }
        assert set(REQUIRED_ERROR_DETAILS.keys()) == expected_codes


# ===========================================================================
# Message-only errors without required details fail normalization
# ===========================================================================


class TestMessageOnlyErrorsFail:
    """Errors with known error_code but missing details produce SCHEMA_VALIDATION_FAILED."""

    def test_protocol_mismatch_no_details(self) -> None:
        """PROTOCOL_MISMATCH with no details dict -> SCHEMA_VALIDATION_FAILED."""
        response = {
            "success": False,
            "error": "Protocol mismatch",
            "error_code": PROTOCOL_MISMATCH,
        }
        result = normalize_error_response(response, "vcad_eval")

        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "expected_protocol" in result["details"]["missing_keys"]
        assert "actual_protocol" in result["details"]["missing_keys"]
        assert result["details"]["original_error_code"] == PROTOCOL_MISMATCH

    def test_source_file_missing_empty_details(self) -> None:
        """SOURCE_FILE_MISSING with empty details -> SCHEMA_VALIDATION_FAILED."""
        response = {
            "success": False,
            "error": "Source file missing",
            "error_code": SOURCE_FILE_MISSING,
            "details": {},
        }
        result = normalize_error_response(response, "vcad_update")

        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "node_id" in result["details"]["missing_keys"]
        assert "source_file" in result["details"]["missing_keys"]
        # operation was filled by normalizer before validation, so not missing
        assert "operation" not in result["details"]["missing_keys"]

    def test_state_reconcile_message_only(self) -> None:
        """STATE_RECONCILE_REQUIRED with message only -> SCHEMA_VALIDATION_FAILED."""
        response = {
            "success": False,
            "error": "Reconciliation needed",
            "error_code": STATE_RECONCILE_REQUIRED,
        }
        result = normalize_error_response(response, "vcad_update_cascade")

        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "drift" in result["details"]["missing_keys"]
        assert "pending_nodes" in result["details"]["missing_keys"]


# ===========================================================================
# Passthrough checks: upstream error_code preserved unchanged
# ===========================================================================


class TestPassthrough:
    """Upstream error_code is preserved unchanged through MCP boundary."""

    def test_upstream_error_code_preserved(self, mock_ctx, mock_vcad) -> None:
        """Sidecar error_code passes through unchanged in MCP tool response."""
        mock_vcad.eval_code.side_effect = VCADRemoteError(
            code=-32000, message="NO_GEOMETRY", data={"node_id": "empty"}
        )

        result = json.loads(vcad_eval(mock_ctx, code="[sphere 0.0]"))

        assert result["success"] is False
        # Upstream code is numeric -32000, not rewritten
        assert result["error_code"] == -32000
        assert result["error"] == "NO_GEOMETRY"

    def test_protocol_mismatch_code_preserved(self, mock_ctx, mock_vcad) -> None:
        """PROTOCOL_MISMATCH error_code preserved through eval tool."""
        mock_vcad.eval_code.side_effect = VCADProtocolError(
            "Protocol version mismatch",
            error_code=PROTOCOL_MISMATCH,
            details={
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
        )

        result = json.loads(vcad_eval(mock_ctx, code="test"))

        assert result["error_code"] == PROTOCOL_MISMATCH

    def test_capability_code_preserved(self, mock_ctx, mock_vcad) -> None:
        """CAPABILITY_UNAVAILABLE error_code preserved through place tool."""
        mock_vcad.eval_file.side_effect = VCADCapabilityError(
            required_capability="adt_cache",
            negotiated_capabilities=["eval"],
            operation="vcad_place",
        )

        result = json.loads(
            vcad_place(mock_ctx, node_id="n1", source_file="/f.skp.oo")
        )

        assert result["error_code"] == CAPABILITY_UNAVAILABLE

    def test_unknown_error_code_passthrough(self) -> None:
        """Error codes not in REQUIRED_ERROR_DETAILS pass through unchanged."""
        response = {
            "success": False,
            "error": "No geometry",
            "error_code": "NO_GEOMETRY",
            "details": {"source_file": "/f.skp.oo"},
        }
        result = normalize_error_response(response, "vcad_place")

        # Not in required map, passes through unchanged
        assert result["error_code"] == "NO_GEOMETRY"
        assert result is response  # Same object, not modified

    def test_no_error_code_passthrough(self) -> None:
        """Responses without error_code pass through unchanged."""
        response = {
            "success": False,
            "error": "Connection refused",
            "error_type": "connection",
        }
        result = normalize_error_response(response, "vcad_eval")

        assert result is response


# ===========================================================================
# Driver enrichment limited to missing details.operation
# ===========================================================================


class TestDriverEnrichment:
    """Driver enrichment is limited to filling missing details.operation."""

    def test_fills_missing_operation(self) -> None:
        """Missing details.operation is filled from the operation parameter."""
        response = {
            "success": False,
            "error": "Protocol mismatch",
            "error_code": PROTOCOL_MISMATCH,
            "details": {
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
        }
        result = normalize_error_response(response, "vcad_place:eval")

        assert result["details"]["operation"] == "vcad_place:eval"

    def test_preserves_existing_operation(self) -> None:
        """Existing details.operation is not overwritten."""
        response = {
            "success": False,
            "error": "Capability missing",
            "error_code": CAPABILITY_UNAVAILABLE,
            "details": {
                "required_capability": "eval",
                "negotiated_capabilities": [],
                "operation": "original_operation",
            },
        }
        result = normalize_error_response(response, "vcad_eval")

        # Original value preserved, not overwritten
        assert result["details"]["operation"] == "original_operation"

    def test_enrichment_via_handle_vcad_error(self, mock_ctx, mock_vcad) -> None:
        """_handle_vcad_error fills operation from the tool operation string."""
        mock_vcad.eval_code.side_effect = VCADProtocolError(
            "Protocol version mismatch",
            error_code=PROTOCOL_MISMATCH,
            details={
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
        )

        result = json.loads(vcad_eval(mock_ctx, code="test"))

        assert result["details"]["operation"] == "vcad_eval"

    def test_does_not_add_extra_keys(self) -> None:
        """Normalizer does not add keys beyond operation."""
        response = {
            "success": False,
            "error": "Capability missing",
            "error_code": CAPABILITY_UNAVAILABLE,
            "details": {
                "required_capability": "eval",
                "negotiated_capabilities": [],
                "operation": "vcad_eval",
                "extra_key": "preserved",
            },
        }
        result = normalize_error_response(response, "vcad_eval")

        # Extra key preserved, no keys removed or added beyond operation
        assert result["details"]["extra_key"] == "preserved"
        assert result["error_code"] == CAPABILITY_UNAVAILABLE


# ===========================================================================
# Negative checks: omit one required detail key -> SCHEMA_VALIDATION_FAILED
# ===========================================================================


class TestNegativeOneMissingKey:
    """Omitting one required detail key triggers SCHEMA_VALIDATION_FAILED."""

    @pytest.mark.parametrize(
        "error_code,complete_details,omit_key",
        [
            (
                PROTOCOL_MISMATCH,
                {"expected_protocol": "1.0", "actual_protocol": "2.0"},
                "expected_protocol",
            ),
            (
                PROTOCOL_MISMATCH,
                {"expected_protocol": "1.0", "actual_protocol": "2.0"},
                "actual_protocol",
            ),
            (
                CAPABILITY_UNAVAILABLE,
                {
                    "required_capability": "eval",
                    "negotiated_capabilities": [],
                    "operation": "op",
                },
                "required_capability",
            ),
            (
                CAPABILITY_UNAVAILABLE,
                {
                    "required_capability": "eval",
                    "negotiated_capabilities": [],
                    "operation": "op",
                },
                "negotiated_capabilities",
            ),
            (
                PATH_NOT_ALLOWED,
                {"path": "/etc", "workspace": "/project", "operation": "op"},
                "path",
            ),
            (
                PATH_NOT_ALLOWED,
                {"path": "/etc", "workspace": "/project", "operation": "op"},
                "workspace",
            ),
            (
                SOURCE_FILE_MISSING,
                {
                    "node_id": "bracket",
                    "source_file": "/f.skp.oo",
                    "operation": "op",
                },
                "node_id",
            ),
            (
                SOURCE_FILE_MISSING,
                {
                    "node_id": "bracket",
                    "source_file": "/f.skp.oo",
                    "operation": "op",
                },
                "source_file",
            ),
            (
                STATE_RECONCILE_REQUIRED,
                {
                    "drift": "diverged",
                    "pending_nodes": ["n1"],
                    "operation": "op",
                },
                "drift",
            ),
            (
                STATE_RECONCILE_REQUIRED,
                {
                    "drift": "diverged",
                    "pending_nodes": ["n1"],
                    "operation": "op",
                },
                "pending_nodes",
            ),
            (
                ARTIFACT_READ_FAILED,
                {
                    "manifest_path": "/path",
                    "reason": "IO error",
                    "operation": "op",
                },
                "manifest_path",
            ),
            (
                ARTIFACT_READ_FAILED,
                {
                    "manifest_path": "/path",
                    "reason": "IO error",
                    "operation": "op",
                },
                "reason",
            ),
        ],
    )
    def test_omit_one_key_triggers_validation_failed(
        self, error_code: str, complete_details: dict, omit_key: str
    ) -> None:
        """Omitting a single required key produces SCHEMA_VALIDATION_FAILED."""
        details = {k: v for k, v in complete_details.items() if k != omit_key}
        response = {
            "success": False,
            "error": "Test error",
            "error_code": error_code,
            "details": details,
        }
        result = normalize_error_response(response, "test_op")

        assert result["error_code"] == SCHEMA_VALIDATION_FAILED
        assert omit_key in result["details"]["missing_keys"]
        assert result["details"]["original_error_code"] == error_code

    def test_omit_operation_filled_by_normalizer(self) -> None:
        """Omitting 'operation' does not fail because normalizer fills it."""
        response = {
            "success": False,
            "error": "Protocol mismatch",
            "error_code": PROTOCOL_MISMATCH,
            "details": {
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
                # operation intentionally omitted
            },
        }
        result = normalize_error_response(response, "vcad_eval")

        # Normalizer fills operation, so all keys present
        assert result["error_code"] == PROTOCOL_MISMATCH
        assert result["details"]["operation"] == "vcad_eval"


# ===========================================================================
# Example fixture validation against schema
# ===========================================================================


class TestExampleFixtureValidation:
    """Example fixtures for each error code validate against error-envelope schema."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "handshake.protocol-mismatch.json",
            "error.capability-unavailable.json",
            "error.path-not-allowed.json",
            "error.source-file-missing.json",
            "error.state-reconcile-required.json",
            "error.artifact-read-failed.json",
        ],
    )
    def test_fixture_validates_against_schema(self, fixture_name: str) -> None:
        """Each error fixture validates against error-envelope.schema.json."""
        fixture = _load_example(fixture_name)
        errors = validate_error_envelope(fixture)
        assert errors == [], f"{fixture_name} validation errors: {errors}"

    @pytest.mark.parametrize(
        "fixture_name,expected_code",
        [
            ("handshake.protocol-mismatch.json", "PROTOCOL_MISMATCH"),
            ("error.capability-unavailable.json", "CAPABILITY_UNAVAILABLE"),
            ("error.path-not-allowed.json", "PATH_NOT_ALLOWED"),
            ("error.source-file-missing.json", "SOURCE_FILE_MISSING"),
            ("error.state-reconcile-required.json", "STATE_RECONCILE_REQUIRED"),
            ("error.artifact-read-failed.json", "ARTIFACT_READ_FAILED"),
        ],
    )
    def test_fixture_has_correct_error_code(
        self, fixture_name: str, expected_code: str
    ) -> None:
        """Each fixture has the expected error_code."""
        fixture = _load_example(fixture_name)
        assert fixture["error_code"] == expected_code

    @pytest.mark.parametrize(
        "fixture_name,expected_code",
        [
            ("handshake.protocol-mismatch.json", "PROTOCOL_MISMATCH"),
            ("error.capability-unavailable.json", "CAPABILITY_UNAVAILABLE"),
            ("error.path-not-allowed.json", "PATH_NOT_ALLOWED"),
            ("error.source-file-missing.json", "SOURCE_FILE_MISSING"),
            ("error.state-reconcile-required.json", "STATE_RECONCILE_REQUIRED"),
            ("error.artifact-read-failed.json", "ARTIFACT_READ_FAILED"),
        ],
    )
    def test_fixture_has_all_required_detail_keys(
        self, fixture_name: str, expected_code: str
    ) -> None:
        """Each fixture includes all required details keys for its error_code."""
        fixture = _load_example(fixture_name)
        required_keys = REQUIRED_ERROR_DETAILS[expected_code]
        details = fixture.get("details", {})
        for key in required_keys:
            assert key in details, (
                f"{fixture_name}: missing required details key '{key}' "
                f"for {expected_code}"
            )


# ===========================================================================
# Schema conditional validation (error-envelope allOf if/then)
# ===========================================================================


class TestSchemaConditionalValidation:
    """Error-envelope schema enforces conditional requirements per error_code."""

    def test_protocol_mismatch_missing_details_fails_schema(self) -> None:
        """PROTOCOL_MISMATCH without details fails schema validation."""
        payload = {
            "success": False,
            "error": "Protocol mismatch",
            "error_code": "PROTOCOL_MISMATCH",
        }
        errors = validate_error_envelope(payload)
        assert len(errors) > 0

    def test_capability_unavailable_missing_required_capability_fails(self) -> None:
        """CAPABILITY_UNAVAILABLE without required_capability fails schema."""
        payload = {
            "success": False,
            "error": "Capability missing",
            "error_code": "CAPABILITY_UNAVAILABLE",
            "details": {
                "negotiated_capabilities": [],
                "operation": "op",
            },
        }
        errors = validate_error_envelope(payload)
        assert len(errors) > 0

    def test_source_file_missing_incomplete_details_fails(self) -> None:
        """SOURCE_FILE_MISSING with partial details fails schema."""
        payload = {
            "success": False,
            "error": "File missing",
            "error_code": "SOURCE_FILE_MISSING",
            "details": {
                "node_id": "bracket",
                # missing source_file and operation
            },
        }
        errors = validate_error_envelope(payload)
        assert len(errors) > 0

    def test_valid_protocol_mismatch_passes_schema(self) -> None:
        """Complete PROTOCOL_MISMATCH passes schema validation."""
        payload = {
            "success": False,
            "error": "Protocol mismatch",
            "error_code": "PROTOCOL_MISMATCH",
            "details": {
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
                "operation": "vcad_eval",
            },
        }
        errors = validate_error_envelope(payload)
        assert errors == []

    def test_unknown_error_code_no_details_required(self) -> None:
        """Unknown error_code passes schema without details."""
        payload = {
            "success": False,
            "error": "Custom error",
            "error_code": "CUSTOM_ERROR",
        }
        errors = validate_error_envelope(payload)
        assert errors == []
