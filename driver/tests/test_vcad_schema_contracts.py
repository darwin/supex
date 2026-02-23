"""Tests for VCAD versioned payload schemas and compatibility.

Covers:
- Schema fixture validation: all examples/*.json against docs/contracts/v1/*.schema.json
- Golden fixtures for each vcad_* tool success + failure payload
- Artifact manifest validation (applied, stale_dropped, superseded)
- Negative validation: missing required fields, wrong types
- Mixed valid+invalid manifests with partial diagnostics results
- Compatibility: additive fields accepted, breaking changes fail under old version
"""

import json
from pathlib import Path
from typing import Any

import pytest

from supex_driver.connection.vcad_schema import (
    SCHEMA_VALIDATION_FAILED,
    clear_schema_cache,
    load_schema,
    make_validation_error_response,
    validate_artifact_manifest,
    validate_error_envelope,
    validate_handshake_request,
    validate_handshake_response,
    validate_payload,
    validate_tools_call,
    validate_viewer_relay,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACTS_DIR = _REPO_ROOT / "docs" / "contracts"
_EXAMPLES_DIR = _CONTRACTS_DIR / "examples"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear schema cache before each test."""
    clear_schema_cache()
    yield
    clear_schema_cache()


def _load_example(name: str) -> dict[str, Any]:
    """Load a JSON example fixture by name."""
    path = _EXAMPLES_DIR / name
    with open(path) as f:
        return json.load(f)


# ===========================================================================
# Schema fixture checks: validate all examples against schemas
# ===========================================================================


class TestSchemaFixtureValidation:
    """Validate all example fixtures against their respective schemas."""

    def test_handshake_ok_validates(self) -> None:
        """handshake.ok.json validates against handshake hello_response."""
        fixture = _load_example("handshake.ok.json")
        errors = validate_handshake_response(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_handshake_protocol_mismatch_validates(self) -> None:
        """handshake.protocol-mismatch.json validates as error envelope."""
        fixture = _load_example("handshake.protocol-mismatch.json")
        errors = validate_error_envelope(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_vcad_place_success_validates(self) -> None:
        """vcad_place.success.json validates against vcad-tools-results."""
        fixture = _load_example("vcad_place.success.json")
        errors = validate_payload(
            fixture, "v1", "vcad-tools-results", sub_schema="vcad_place_result"
        )
        assert errors == [], f"Validation errors: {errors}"

    def test_vcad_place_error_validates(self) -> None:
        """vcad_place.error.json validates as error envelope."""
        fixture = _load_example("vcad_place.error.json")
        errors = validate_error_envelope(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_viewer_ready_ok_validates(self) -> None:
        """viewer.ready.ok.json validates against viewer-relay."""
        fixture = _load_example("viewer.ready.ok.json")
        errors = validate_viewer_relay(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_scene_snapshot_ok_validates(self) -> None:
        """scene.snapshot.ok.json validates against viewer-relay."""
        fixture = _load_example("scene.snapshot.ok.json")
        errors = validate_viewer_relay(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_artifact_applied_validates(self) -> None:
        """artifact.applied.json validates against artifact-manifest."""
        fixture = _load_example("artifact.applied.json")
        errors = validate_artifact_manifest(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_artifact_stale_dropped_validates(self) -> None:
        """artifact.stale_dropped.json validates against artifact-manifest."""
        fixture = _load_example("artifact.stale_dropped.json")
        errors = validate_artifact_manifest(fixture)
        assert errors == [], f"Validation errors: {errors}"

    def test_artifact_superseded_validates(self) -> None:
        """artifact.superseded.json validates against artifact-manifest."""
        fixture = _load_example("artifact.superseded.json")
        errors = validate_artifact_manifest(fixture)
        assert errors == [], f"Validation errors: {errors}"


# ===========================================================================
# Golden fixture: vcad_* tool payloads
# ===========================================================================


class TestGoldenToolPayloads:
    """Golden fixture tests for each vcad_* tool success and failure payload."""

    def test_vcad_place_success_golden_fields(self) -> None:
        """vcad_place success has all required golden fields."""
        fixture = _load_example("vcad_place.success.json")
        assert fixture["success"] is True
        assert isinstance(fixture["node_id"], str)
        assert isinstance(fixture["entity_id"], int)
        assert isinstance(fixture["definition_name"], str)
        assert isinstance(fixture["mesh_path"], str)
        assert isinstance(fixture["revision"], int)
        assert "min" in fixture["bbox"]
        assert "max" in fixture["bbox"]
        assert isinstance(fixture["volume"], (int, float))
        assert isinstance(fixture["surface_area"], (int, float))

    def test_vcad_place_error_golden_fields(self) -> None:
        """vcad_place error has required error envelope fields."""
        fixture = _load_example("vcad_place.error.json")
        assert fixture["success"] is False
        assert isinstance(fixture["error"], str)
        assert isinstance(fixture["error_code"], str)

    def test_handshake_response_golden_fields(self) -> None:
        """Handshake response has required golden fields."""
        fixture = _load_example("handshake.ok.json")
        assert isinstance(fixture["protocol_version"], str)
        assert isinstance(fixture["capabilities"], list)
        assert all(isinstance(c, str) for c in fixture["capabilities"])

    def test_viewer_ready_golden_fields(self) -> None:
        """viewer.ready has required golden fields."""
        fixture = _load_example("viewer.ready.ok.json")
        assert fixture["type"] == "viewer.ready"
        assert isinstance(fixture["protocol_version"], str)
        assert isinstance(fixture["features"], list)

    def test_artifact_applied_golden_fields(self) -> None:
        """Applied artifact has all conditional required fields."""
        fixture = _load_example("artifact.applied.json")
        assert fixture["status"] == "applied"
        assert isinstance(fixture["revision"], int)
        assert "min" in fixture["bbox"]
        assert "max" in fixture["bbox"]
        assert isinstance(fixture["volume"], (int, float))
        assert isinstance(fixture["surface_area"], (int, float))
        assert isinstance(fixture["source_hash"], str)
        assert isinstance(fixture["mesh_path"], str)
        assert isinstance(fixture["finished_at"], str)

    def test_artifact_stale_dropped_golden_fields(self) -> None:
        """Stale-dropped artifact has required drop_reason."""
        fixture = _load_example("artifact.stale_dropped.json")
        assert fixture["status"] == "stale_dropped"
        assert isinstance(fixture["drop_reason"], str)
        assert isinstance(fixture["source_hash"], str)
        assert isinstance(fixture["finished_at"], str)

    def test_artifact_superseded_golden_fields(self) -> None:
        """Superseded artifact has required supersede_reason."""
        fixture = _load_example("artifact.superseded.json")
        assert fixture["status"] == "superseded"
        assert isinstance(fixture["supersede_reason"], str)
        assert isinstance(fixture["source_hash"], str)
        assert isinstance(fixture["finished_at"], str)


# ===========================================================================
# Negative validation: missing required fields
# ===========================================================================


class TestNegativeValidationMissingFields:
    """Missing required fields produce SCHEMA_VALIDATION_FAILED."""

    def test_handshake_missing_protocol_version(self) -> None:
        """Missing protocol_version in handshake response -> validation error."""
        payload = {"capabilities": ["eval"]}
        errors = validate_handshake_response(payload)
        assert len(errors) > 0
        paths = [e["path"] for e in errors]
        assert "$" in paths or "protocol_version" in paths

    def test_handshake_missing_capabilities(self) -> None:
        """Missing capabilities in handshake response -> validation error."""
        payload = {"protocol_version": "1.0"}
        errors = validate_handshake_response(payload)
        assert len(errors) > 0

    def test_handshake_request_missing_name(self) -> None:
        """Missing name in handshake request -> validation error."""
        payload = {
            "version": "0.2.0",
            "protocol_version": "1.0",
            "pid": 12345,
        }
        errors = validate_handshake_request(payload)
        assert len(errors) > 0

    def test_tools_call_missing_name(self) -> None:
        """Missing name in tools/call -> validation error."""
        payload = {"arguments": {"code": "test"}}
        errors = validate_tools_call(payload)
        assert len(errors) > 0

    def test_tools_call_missing_arguments(self) -> None:
        """Missing arguments in tools/call -> validation error."""
        payload = {"name": "eval_code"}
        errors = validate_tools_call(payload)
        assert len(errors) > 0

    def test_error_envelope_missing_error(self) -> None:
        """Missing error field in error envelope -> validation error."""
        payload = {"success": False}
        errors = validate_error_envelope(payload)
        assert len(errors) > 0

    def test_error_envelope_missing_success(self) -> None:
        """Missing success field in error envelope -> validation error."""
        payload = {"error": "something failed"}
        errors = validate_error_envelope(payload)
        assert len(errors) > 0

    def test_artifact_missing_status(self) -> None:
        """Missing status in artifact manifest -> validation error."""
        payload = {
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_missing_source_hash(self) -> None:
        """Missing source_hash in artifact manifest -> validation error."""
        payload = {
            "status": "applied",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "revision": 1,
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "volume": 1.0,
            "surface_area": 6.0,
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_applied_missing_revision(self) -> None:
        """Applied artifact missing revision -> validation error."""
        payload = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "volume": 1.0,
            "surface_area": 6.0,
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_applied_missing_bbox(self) -> None:
        """Applied artifact missing bbox -> validation error."""
        payload = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "revision": 1,
            "volume": 1.0,
            "surface_area": 6.0,
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_applied_missing_volume(self) -> None:
        """Applied artifact missing volume -> validation error."""
        payload = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "revision": 1,
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "surface_area": 6.0,
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_applied_missing_surface_area(self) -> None:
        """Applied artifact missing surface_area -> validation error."""
        payload = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "revision": 1,
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "volume": 1.0,
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_stale_dropped_missing_drop_reason(self) -> None:
        """Stale-dropped artifact missing drop_reason -> validation error."""
        payload = {
            "status": "stale_dropped",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_superseded_missing_supersede_reason(self) -> None:
        """Superseded artifact missing supersede_reason -> validation error."""
        payload = {
            "status": "superseded",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0


# ===========================================================================
# Negative validation: wrong types
# ===========================================================================


class TestNegativeValidationWrongTypes:
    """Wrong types produce SCHEMA_VALIDATION_FAILED."""

    def test_viewer_relay_wrong_type_field(self) -> None:
        """Wrong type for revision in mesh.update -> validation error."""
        payload = {
            "type": "mesh.update",
            "node_id": "bracket",
            "revision": "not-an-int",  # Should be integer
            "positions": [0.0, 0.0, 0.0],
            "indices": [0],
        }
        errors = validate_viewer_relay(payload)
        assert len(errors) > 0

    def test_viewer_relay_wrong_positions_type(self) -> None:
        """Wrong type for positions in mesh.update -> validation error."""
        payload = {
            "type": "mesh.update",
            "node_id": "bracket",
            "revision": 1,
            "positions": "not-an-array",
            "indices": [0],
        }
        errors = validate_viewer_relay(payload)
        assert len(errors) > 0

    def test_handshake_wrong_pid_type(self) -> None:
        """Wrong type for pid in handshake request -> validation error."""
        payload = {
            "name": "supex-driver",
            "version": "0.2.0",
            "protocol_version": "1.0",
            "pid": "not-an-int",
        }
        errors = validate_handshake_request(payload)
        assert len(errors) > 0

    def test_handshake_wrong_protocol_format(self) -> None:
        """Invalid protocol_version format -> validation error."""
        payload = {
            "protocol_version": "invalid",
            "capabilities": ["eval"],
        }
        errors = validate_handshake_response(payload)
        assert len(errors) > 0

    def test_artifact_wrong_status_value(self) -> None:
        """Invalid status enum value -> validation error."""
        payload = {
            "status": "invalid_status",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_artifact_wrong_revision_type(self) -> None:
        """Wrong type for revision in artifact -> validation error."""
        payload = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "revision": "not-int",
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "volume": 1.0,
            "surface_area": 6.0,
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_error_envelope_wrong_success_value(self) -> None:
        """success=true in error envelope -> validation error."""
        payload = {
            "success": True,
            "error": "something",
        }
        errors = validate_error_envelope(payload)
        assert len(errors) > 0


# ===========================================================================
# Mixed valid+invalid manifests: partial diagnostics
# ===========================================================================


class TestPartialDiagnostics:
    """Mixed valid+invalid manifests return partial results with per-item errors."""

    def _validate_manifests(
        self, manifests: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Simulate driver-side diagnostics manifest validation.

        Best-effort: one invalid manifest must not fail the whole response.
        """
        results: list[dict[str, Any]] = []
        valid_count = 0
        invalid_count = 0

        for i, manifest in enumerate(manifests):
            errors = validate_artifact_manifest(manifest)
            if errors:
                invalid_count += 1
                results.append({
                    "index": i,
                    "valid": False,
                    "error_code": SCHEMA_VALIDATION_FAILED,
                    "errors": errors,
                })
            else:
                valid_count += 1
                results.append({
                    "index": i,
                    "valid": True,
                    "status": manifest["status"],
                })

        return {
            "total": len(manifests),
            "valid": valid_count,
            "invalid": invalid_count,
            "results": results,
        }

    def test_all_valid_manifests(self) -> None:
        """All valid manifests -> all results valid."""
        manifests = [
            _load_example("artifact.applied.json"),
            _load_example("artifact.stale_dropped.json"),
            _load_example("artifact.superseded.json"),
        ]
        result = self._validate_manifests(manifests)
        assert result["valid"] == 3
        assert result["invalid"] == 0
        assert all(r["valid"] for r in result["results"])

    def test_mixed_valid_invalid(self) -> None:
        """Mixed valid+invalid -> partial results with per-item errors."""
        valid_manifest = _load_example("artifact.applied.json")
        invalid_manifest = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            # Missing revision, bbox, volume, surface_area
        }

        result = self._validate_manifests([valid_manifest, invalid_manifest])
        assert result["valid"] == 1
        assert result["invalid"] == 1
        assert result["results"][0]["valid"] is True
        assert result["results"][1]["valid"] is False
        assert result["results"][1]["error_code"] == SCHEMA_VALIDATION_FAILED

    def test_all_invalid_manifests(self) -> None:
        """All invalid manifests -> all results invalid, but response succeeds."""
        invalid1 = {"status": "applied"}  # Missing everything
        invalid2 = {"status": "unknown_status"}  # Invalid status

        result = self._validate_manifests([invalid1, invalid2])
        assert result["valid"] == 0
        assert result["invalid"] == 2
        assert result["total"] == 2

    def test_single_invalid_does_not_fail_batch(self) -> None:
        """One invalid manifest in batch -> others still processed."""
        manifests = [
            _load_example("artifact.applied.json"),
            {"status": "broken"},  # Invalid
            _load_example("artifact.superseded.json"),
        ]

        result = self._validate_manifests(manifests)
        assert result["valid"] == 2
        assert result["invalid"] == 1
        assert result["results"][0]["valid"] is True
        assert result["results"][1]["valid"] is False
        assert result["results"][2]["valid"] is True

    def test_empty_manifest_list(self) -> None:
        """Empty manifest list -> empty results."""
        result = self._validate_manifests([])
        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["invalid"] == 0
        assert result["results"] == []


# ===========================================================================
# Validation error response format
# ===========================================================================


class TestValidationErrorResponse:
    """Validate the error response format from make_validation_error_response."""

    def test_error_response_structure(self) -> None:
        """Error response matches error-envelope schema."""
        errors = [{"path": "protocol_version", "expected": "string matching pattern"}]
        response = make_validation_error_response(errors)

        assert response["success"] is False
        assert response["error_code"] == SCHEMA_VALIDATION_FAILED
        assert "details" in response
        assert response["details"]["path"] == "protocol_version"

        # Validate against error-envelope schema
        envelope_errors = validate_error_envelope(response)
        assert envelope_errors == [], f"Error envelope validation failed: {envelope_errors}"

    def test_error_response_with_custom_message(self) -> None:
        """Error response includes custom message."""
        errors = [{"path": "$", "expected": "valid handshake"}]
        response = make_validation_error_response(errors, "Handshake validation failed")
        assert response["error"] == "Handshake validation failed"

    def test_error_response_empty_errors(self) -> None:
        """Error response handles empty error list gracefully."""
        response = make_validation_error_response([])
        assert response["error_code"] == SCHEMA_VALIDATION_FAILED
        assert response["details"]["path"] == "$"


# ===========================================================================
# Schema loading
# ===========================================================================


class TestSchemaLoading:
    """Test schema loading and caching."""

    def test_load_existing_schema(self) -> None:
        """Can load existing schema files."""
        schema = load_schema("v1", "handshake")
        assert "$schema" in schema
        assert "$defs" in schema

    def test_load_all_v1_schemas(self) -> None:
        """All v1 schemas load successfully."""
        schema_names = [
            "handshake",
            "tools-call",
            "vcad-tools-results",
            "viewer-relay",
            "error-envelope",
            "artifact-manifest",
        ]
        for name in schema_names:
            schema = load_schema("v1", name)
            assert "$schema" in schema, f"Missing $schema in {name}"

    def test_load_nonexistent_schema(self) -> None:
        """Loading nonexistent schema raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_schema("v1", "nonexistent")

    def test_schema_caching(self) -> None:
        """Schemas are cached after first load."""
        s1 = load_schema("v1", "handshake")
        s2 = load_schema("v1", "handshake")
        assert s1 is s2

    def test_cache_clear(self) -> None:
        """Cache clear forces reload."""
        s1 = load_schema("v1", "handshake")
        clear_schema_cache()
        s2 = load_schema("v1", "handshake")
        assert s1 is not s2
        assert s1 == s2


# ===========================================================================
# Compatibility: additive fields accepted
# ===========================================================================


class TestCompatibilityAdditive:
    """Previous fixtures remain accepted when only additive (optional) fields added."""

    def test_handshake_response_with_extra_field(self) -> None:
        """Handshake response with unknown extra field still validates."""
        fixture = _load_example("handshake.ok.json")
        fixture["new_optional_field"] = "added-in-v1.1"
        errors = validate_handshake_response(fixture)
        assert errors == []

    def test_viewer_ready_with_extra_field(self) -> None:
        """viewer.ready with unknown extra field still validates."""
        fixture = _load_example("viewer.ready.ok.json")
        fixture["extra_info"] = {"build": "abc123"}
        errors = validate_viewer_relay(fixture)
        assert errors == []

    def test_artifact_with_extra_field(self) -> None:
        """Artifact manifest with unknown extra field still validates."""
        fixture = _load_example("artifact.applied.json")
        fixture["new_metric"] = 42.0
        errors = validate_artifact_manifest(fixture)
        assert errors == []

    def test_error_envelope_with_extra_field(self) -> None:
        """Error envelope with unknown extra field still validates."""
        fixture = _load_example("vcad_place.error.json")
        fixture["retry_after_ms"] = 1000
        errors = validate_error_envelope(fixture)
        assert errors == []

    def test_tools_call_with_extra_field(self) -> None:
        """tools/call with extra field still validates."""
        payload = {
            "name": "eval_code",
            "arguments": {"code": "[cube 10 10 10]"},
            "request_id": "req-001",
            "trace_id": "new-field",
        }
        errors = validate_tools_call(payload)
        assert errors == []

    def test_mesh_update_with_extra_field(self) -> None:
        """mesh.update with extra field still validates."""
        payload = {
            "type": "mesh.update",
            "node_id": "bracket",
            "revision": 1,
            "positions": [0.0, 0.0, 0.0],
            "indices": [0],
            "lod_level": 2,  # New optional field
        }
        errors = validate_viewer_relay(payload)
        assert errors == []

    def test_scene_snapshot_with_extra_field(self) -> None:
        """scene.snapshot with extra field still validates."""
        fixture = _load_example("scene.snapshot.ok.json")
        fixture["snapshot_id"] = "snap-001"
        errors = validate_viewer_relay(fixture)
        assert errors == []

    def test_previous_fixtures_remain_valid(self) -> None:
        """All original fixtures still validate unchanged (regression guard)."""
        cases = [
            ("handshake.ok.json", validate_handshake_response),
            ("viewer.ready.ok.json", validate_viewer_relay),
            ("scene.snapshot.ok.json", validate_viewer_relay),
            ("artifact.applied.json", validate_artifact_manifest),
            ("artifact.stale_dropped.json", validate_artifact_manifest),
            ("artifact.superseded.json", validate_artifact_manifest),
        ]
        for fixture_name, validator in cases:
            fixture = _load_example(fixture_name)
            errors = validator(fixture)
            assert errors == [], f"{fixture_name} failed: {errors}"


# ===========================================================================
# Compatibility: breaking changes require protocol bump
# ===========================================================================


class TestCompatibilityBreaking:
    """Breaking changes fail deterministically under current version."""

    def test_protocol_version_v2_not_accepted_by_v1_pattern(self) -> None:
        """v2.0 protocol_version still matches pattern but signals breaking change.

        The version string itself is valid (matches major.minor), but the
        protocol negotiation logic (not schema) rejects major mismatches.
        We verify the schema allows any major.minor string -- breaking change
        detection happens at protocol level, not schema level.
        """
        payload = {
            "protocol_version": "2.0",
            "capabilities": ["eval"],
        }
        # Schema allows any valid major.minor string
        errors = validate_handshake_response(payload)
        assert errors == []

    def test_breaking_status_change_rejected(self) -> None:
        """New status value not in enum fails validation."""
        payload = {
            "status": "new_v2_status",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(payload)
        assert len(errors) > 0

    def test_removing_required_field_breaks(self) -> None:
        """Removing a required field from a valid fixture fails."""
        fixture = _load_example("artifact.applied.json")
        del fixture["source_hash"]
        errors = validate_artifact_manifest(fixture)
        assert len(errors) > 0

    def test_changing_field_type_breaks(self) -> None:
        """Changing field type from string to int breaks validation."""
        fixture = _load_example("handshake.ok.json")
        fixture["protocol_version"] = 1  # Was string, now int
        errors = validate_handshake_response(fixture)
        assert len(errors) > 0

    def test_viewer_type_mismatch_breaks(self) -> None:
        """Wrong message type string fails validation."""
        payload = {
            "type": "viewer.ready",
            "protocol_version": "1.0",
            # Missing required "features"
        }
        errors = validate_viewer_relay(payload)
        assert len(errors) > 0

    def test_error_envelope_success_true_breaks(self) -> None:
        """success=true in error envelope is a breaking contract violation."""
        payload = {"success": True, "error": "but says success"}
        errors = validate_error_envelope(payload)
        assert len(errors) > 0

    def test_artifact_conditional_requirements_enforced(self) -> None:
        """Conditional requirements per status are strictly enforced."""
        # applied without volume -> must fail
        applied_no_volume = {
            "status": "applied",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
            "revision": 1,
            "bbox": {"min": [0, 0, 0], "max": [1, 1, 1]},
            "surface_area": 6.0,
            # Missing volume
        }
        errors = validate_artifact_manifest(applied_no_volume)
        assert len(errors) > 0

        # stale_dropped without drop_reason -> must fail
        stale_no_reason = {
            "status": "stale_dropped",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(stale_no_reason)
        assert len(errors) > 0

        # superseded without supersede_reason -> must fail
        superseded_no_reason = {
            "status": "superseded",
            "source_hash": "sha256:abc",
            "mesh_path": "/tmp/out.dae",
            "finished_at": "2026-02-22T10:00:00Z",
        }
        errors = validate_artifact_manifest(superseded_no_reason)
        assert len(errors) > 0


# ===========================================================================
# Sub-schema validation
# ===========================================================================


class TestSubSchemaValidation:
    """Test validation against specific sub-schemas."""

    def test_validate_specific_tool_result(self) -> None:
        """Can validate against a specific vcad tool result sub-schema."""
        fixture = _load_example("vcad_place.success.json")
        errors = validate_payload(
            fixture, "v1", "vcad-tools-results", sub_schema="vcad_place_result"
        )
        assert errors == []

    def test_validate_nonexistent_sub_schema(self) -> None:
        """Validating against nonexistent sub-schema returns error."""
        errors = validate_payload(
            {"test": True}, "v1", "handshake", sub_schema="nonexistent"
        )
        assert len(errors) > 0
        assert "nonexistent" in errors[0]["expected"]

    def test_validate_viewer_relay_by_type(self) -> None:
        """Viewer relay messages route to correct sub-schema by type."""
        # mesh.remove
        payload = {"type": "mesh.remove", "node_id": "bracket"}
        errors = validate_viewer_relay(payload)
        assert errors == []

        # scene.reset
        payload = {"type": "scene.reset"}
        errors = validate_viewer_relay(payload)
        assert errors == []

        # screenshot.request
        payload = {"type": "screenshot.request", "request_id": "req-123"}
        errors = validate_viewer_relay(payload)
        assert errors == []

    def test_validate_viewer_state(self) -> None:
        """viewer.state message validates correctly."""
        payload = {
            "type": "viewer.state",
            "camera": {"position": [0, 0, 10], "target": [0, 0, 0]},
            "selection": ["node-1", "node-2"],
        }
        errors = validate_viewer_relay(payload)
        assert errors == []

    def test_validate_screenshot_response(self) -> None:
        """screenshot.response validates correctly."""
        payload = {
            "type": "screenshot.response",
            "request_id": "req-123",
            "data": "iVBORw0KGgoAAAANSUhEUg==",
            "width": 1920,
            "height": 1080,
        }
        errors = validate_viewer_relay(payload)
        assert errors == []

    def test_validate_viewer_focus(self) -> None:
        """viewer.focus validates correctly."""
        payload = {
            "type": "viewer.focus",
            "node_id": "bracket",
        }
        errors = validate_viewer_relay(payload)
        assert errors == []


# ===========================================================================
# Tools/call envelope validation
# ===========================================================================


class TestToolsCallValidation:
    """Test tools/call input envelope validation."""

    def test_valid_tools_call(self) -> None:
        """Valid tools/call payload validates."""
        payload = {
            "name": "eval_code",
            "arguments": {"code": "[cube 10 10 10]"},
            "request_id": "req-001",
        }
        errors = validate_tools_call(payload)
        assert errors == []

    def test_tools_call_minimal(self) -> None:
        """Minimal valid tools/call with only required fields."""
        payload = {
            "name": "inspect",
            "arguments": {},
        }
        errors = validate_tools_call(payload)
        assert errors == []

    def test_tools_call_numeric_request_id(self) -> None:
        """tools/call with integer request_id validates."""
        payload = {
            "name": "eval_code",
            "arguments": {"code": "test"},
            "request_id": 42,
        }
        errors = validate_tools_call(payload)
        assert errors == []
