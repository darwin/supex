"""Tests for VCAD artifact manifest: deterministic eval artifacts, visibility and diagnostics.

Covers:
- Reproducibility: same input/revision yields stable manifest keys and source_hash
- Status-path: stale/superseded eval paths write manifest with correct terminal status
- Retention pairing: cleanup removes mesh-artifact/manifest pairs together (no orphans)
- Atomic pair commit: inject failure between publish steps -> no committed mesh-without-manifest
- Crash recovery: restart scan resolves pending/incomplete pairs
- Path hardening: traversal/symlink attempts fail with PATH_NOT_ALLOWED
- Committed visibility: interrupted pair publish -> committed list consistent
- Diagnostics reader: mixed valid/invalid/missing manifests -> partial success + per-item errors
- Diagnostics integration: vcad_metrics returns last_artifact_manifest when available
- Compatibility: additive manifest fields accepted by parser/schema without protocol bump
"""

import json
import os
import time

import pytest

from supex_driver.connection.vcad_artifact_manifest import (
    MANIFEST_EXT,
    PAIR_PENDING_EXT,
    TMP_SUFFIX,
    ArtifactManifest,
    ArtifactStore,
    _reset_artifact_store,
    build_applied_manifest,
    build_stale_dropped_manifest,
    build_superseded_manifest,
    compute_source_hash,
    manifest_path_for,
    pending_marker_for,
    validate_artifact_path,
)
from supex_driver.connection.vcad_metrics import (
    _reset_vcad_metrics,
    get_vcad_metrics,
)
from supex_driver.connection.vcad_schema import (
    validate_artifact_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset global singletons before each test."""
    _reset_vcad_metrics()
    _reset_artifact_store()
    yield
    _reset_vcad_metrics()
    _reset_artifact_store()


@pytest.fixture
def artifact_root(tmp_path):
    """Temporary artifact root directory."""
    root = str(tmp_path / "artifacts")
    os.makedirs(root, exist_ok=True)
    return root


@pytest.fixture
def store(artifact_root):
    """Create a fresh ArtifactStore."""
    return ArtifactStore(artifact_root, max_retained=10)


def _make_mesh_content(label: str = "test") -> bytes:
    """Create minimal mesh file content for tests."""
    return f"<COLLADA>{label}</COLLADA>".encode()


def _make_applied_manifest(
    store: ArtifactStore,
    node_id: str = "node-1",
    revision: int = 1,
    label: str = "test",
    source: str = "[cube 10.0 10.0 10.0]",
    finished_at: float | None = None,
) -> ArtifactManifest:
    """Build an applied manifest for testing."""
    mesh_path = os.path.join(store.artifact_root, f"{node_id}-r{revision}.dae")
    return build_applied_manifest(
        node_id=node_id,
        revision=revision,
        request_id=f"req-{label}",
        source_file=f"/project/{node_id}.cmp.oo",
        source_hash=compute_source_hash(source),
        mesh_path=mesh_path,
        imports=[],
        bbox={"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
        volume=1000.0,
        surface_area=600.0,
        queued_at=1700000000.0,
        started_at=1700000001.0,
        finished_at=finished_at or 1700000002.0,
        eval_duration_ms=1000.0,
    )


# ===========================================================================
# Reproducibility
# ===========================================================================


class TestReproducibility:
    """Same input/revision yields stable manifest keys and source_hash."""

    def test_same_source_same_hash(self) -> None:
        """Identical source content produces identical hash."""
        source = "[cube 50.0 30.0 5.0]"
        h1 = compute_source_hash(source)
        h2 = compute_source_hash(source)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_source_different_hash(self) -> None:
        """Different source content produces different hash."""
        h1 = compute_source_hash("[cube 50.0 30.0 5.0]")
        h2 = compute_source_hash("[cube 50.0 30.0 6.0]")
        assert h1 != h2

    def test_stable_manifest_serialization(self, store: ArtifactStore) -> None:
        """Same manifest produces identical JSON output."""
        m1 = _make_applied_manifest(store, finished_at=1700000002.0)
        m2 = _make_applied_manifest(store, finished_at=1700000002.0)

        d1 = m1.to_dict()
        d2 = m2.to_dict()
        assert d1 == d2

    def test_manifest_roundtrip(self, store: ArtifactStore) -> None:
        """Manifest survives dict roundtrip."""
        manifest = _make_applied_manifest(store)
        d = manifest.to_dict()
        restored = ArtifactManifest.from_dict(d)
        assert restored.to_dict() == d

    def test_manifest_json_deterministic(self, store: ArtifactStore) -> None:
        """JSON serialization is deterministic."""
        manifest = _make_applied_manifest(store, finished_at=1700000002.0)
        j1 = json.dumps(manifest.to_dict(), sort_keys=False)
        j2 = json.dumps(manifest.to_dict(), sort_keys=False)
        assert j1 == j2

    def test_finished_at_rfc3339_format(self, store: ArtifactStore) -> None:
        """finished_at is in RFC3339 UTC format."""
        manifest = _make_applied_manifest(store, finished_at=1700000002.0)
        assert manifest.finished_at.endswith("Z")
        assert "T" in manifest.finished_at


# ===========================================================================
# Status-path: terminal status manifests
# ===========================================================================


class TestStatusPaths:
    """Stale/superseded eval paths write manifest with correct terminal status."""

    def test_applied_status(self, store: ArtifactStore) -> None:
        manifest = _make_applied_manifest(store)
        d = manifest.to_dict()
        assert d["status"] == "applied"
        assert "revision" in d
        assert "bbox" in d
        assert "volume" in d
        assert "surface_area" in d

    def test_stale_dropped_status(self, artifact_root: str) -> None:
        mesh_path = os.path.join(artifact_root, "node-1-r1.dae")
        manifest = build_stale_dropped_manifest(
            node_id="node-1",
            revision=1,
            request_id="req-1",
            source_file="/project/node-1.cmp.oo",
            source_hash=compute_source_hash("[cube 10.0 10.0 10.0]"),
            mesh_path=mesh_path,
            drop_reason="revision 2 is current, result for revision 1 is stale",
            finished_at=1700000002.0,
        )
        d = manifest.to_dict()
        assert d["status"] == "stale_dropped"
        assert "drop_reason" in d
        assert "stale" in d["drop_reason"]

    def test_superseded_status(self, artifact_root: str) -> None:
        mesh_path = os.path.join(artifact_root, "node-1-r1.dae")
        manifest = build_superseded_manifest(
            node_id="node-1",
            revision=1,
            request_id="req-1",
            source_file="/project/node-1.cmp.oo",
            source_hash=compute_source_hash("[cube 10.0 10.0 10.0]"),
            mesh_path=mesh_path,
            supersede_reason="newer revision enqueued",
            superseded_by_revision=3,
            finished_at=1700000002.0,
        )
        d = manifest.to_dict()
        assert d["status"] == "superseded"
        assert "supersede_reason" in d
        assert d["superseded_by_revision"] == 3

    def test_stale_manifest_validates_against_schema(self, artifact_root: str) -> None:
        mesh_path = os.path.join(artifact_root, "stale.dae")
        manifest = build_stale_dropped_manifest(
            node_id="node-1",
            revision=1,
            request_id="req-1",
            source_file="/project/node-1.cmp.oo",
            source_hash=compute_source_hash("[cube 10.0 10.0 10.0]"),
            mesh_path=mesh_path,
            drop_reason="stale revision",
        )
        errors = validate_artifact_manifest(manifest.to_dict())
        assert errors == [], f"Validation errors: {errors}"

    def test_superseded_manifest_validates_against_schema(
        self, artifact_root: str
    ) -> None:
        mesh_path = os.path.join(artifact_root, "superseded.dae")
        manifest = build_superseded_manifest(
            node_id="node-1",
            revision=1,
            request_id="req-1",
            source_file="/project/node-1.cmp.oo",
            source_hash=compute_source_hash("[cube 10.0 10.0 10.0]"),
            mesh_path=mesh_path,
            supersede_reason="newer revision enqueued",
            superseded_by_revision=2,
        )
        errors = validate_artifact_manifest(manifest.to_dict())
        assert errors == [], f"Validation errors: {errors}"

    def test_applied_manifest_validates_against_schema(
        self, store: ArtifactStore
    ) -> None:
        manifest = _make_applied_manifest(store)
        errors = validate_artifact_manifest(manifest.to_dict())
        assert errors == [], f"Validation errors: {errors}"


# ===========================================================================
# Retention pairing
# ===========================================================================


class TestRetentionPairing:
    """Cleanup removes mesh-artifact/manifest pairs together (no orphans)."""

    def test_retention_removes_oldest_pairs(self) -> None:
        """When max_retained is exceeded, oldest pairs are removed."""
        import tempfile

        root = tempfile.mkdtemp()
        store = ArtifactStore(root, max_retained=3)

        # Write 5 artifacts
        for i in range(5):
            manifest = build_applied_manifest(
                node_id=f"node-{i}",
                revision=1,
                request_id=f"req-{i}",
                source_file=f"/project/node-{i}.cmp.oo",
                source_hash=compute_source_hash(f"[cube {i}.0 10.0 10.0]"),
                mesh_path=os.path.join(root, f"node-{i}-r1.dae"),
                bbox={"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0]},
                volume=1000.0,
                surface_area=600.0,
                finished_at=1700000000.0 + i,
            )
            store.write_artifact_pair(manifest, _make_mesh_content(f"mesh-{i}"))
            time.sleep(0.01)  # ensure different mtimes

        # Only 3 should remain
        committed = store.list_committed_artifacts()
        assert len(committed) == 3

    def test_no_orphan_manifests(self, store: ArtifactStore) -> None:
        """After pair removal, no manifest files without mesh files."""
        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        mesh_path = manifest.mesh_path
        store.remove_artifact_pair(mesh_path)

        assert not os.path.exists(mesh_path)
        assert not os.path.exists(manifest_path_for(mesh_path))

    def test_no_orphan_mesh_files(self, store: ArtifactStore) -> None:
        """After pair removal, no mesh files without manifest files."""
        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        # Manually delete only the manifest
        m_path = manifest_path_for(manifest.mesh_path)
        os.unlink(m_path)

        # Not committed anymore
        assert not store.is_committed(manifest.mesh_path)


# ===========================================================================
# Atomic pair commit
# ===========================================================================


class TestAtomicPairCommit:
    """Inject failure between publish steps -> no committed mesh-without-manifest."""

    def test_pending_marker_blocks_committed(self, store: ArtifactStore) -> None:
        """Artifact with pending marker is not committed."""
        manifest = _make_applied_manifest(store)
        mesh_path = manifest.mesh_path

        # Write mesh and manifest manually
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())
        m_path = manifest_path_for(mesh_path)
        with open(m_path, "w") as f:
            json.dump(manifest.to_dict(), f)

        # Create pending marker
        marker = pending_marker_for(mesh_path)
        with open(marker, "w") as f:
            f.write("pending")

        assert not store.is_committed(mesh_path)
        assert mesh_path not in store.list_committed_artifacts()

    def test_committed_after_marker_removed(self, store: ArtifactStore) -> None:
        """Artifact becomes committed after pending marker is removed."""
        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        assert store.is_committed(manifest.mesh_path)
        assert manifest.mesh_path in store.list_committed_artifacts()

    def test_mesh_without_manifest_not_committed(
        self, store: ArtifactStore
    ) -> None:
        """Mesh file alone (without manifest) is not committed."""
        mesh_path = os.path.join(store.artifact_root, "orphan.dae")
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        assert not store.is_committed(mesh_path)

    def test_manifest_without_mesh_not_committed(
        self, store: ArtifactStore
    ) -> None:
        """Manifest file alone (without mesh) is not committed."""
        mesh_path = os.path.join(store.artifact_root, "orphan.dae")
        m_path = manifest_path_for(mesh_path)
        manifest = _make_applied_manifest(store)
        with open(m_path, "w") as f:
            json.dump(manifest.to_dict(), f)

        assert not store.is_committed(mesh_path)

    def test_successful_write_creates_both_files(
        self, store: ArtifactStore
    ) -> None:
        """write_artifact_pair creates both mesh and manifest."""
        manifest = _make_applied_manifest(store)
        m_path = store.write_artifact_pair(manifest, _make_mesh_content())

        assert os.path.exists(manifest.mesh_path)
        assert os.path.exists(m_path)
        assert not os.path.exists(pending_marker_for(manifest.mesh_path))

    def test_no_tmp_files_after_successful_write(
        self, store: ArtifactStore
    ) -> None:
        """No staged .tmp files remain after successful write."""
        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        tmp_files = [
            f
            for f in os.listdir(store.artifact_root)
            if f.endswith(TMP_SUFFIX)
        ]
        assert tmp_files == []


# ===========================================================================
# Crash recovery
# ===========================================================================


class TestCrashRecovery:
    """Restart sidecar -> recovery scan resolves pending/incomplete pairs."""

    def test_recovery_cleans_incomplete_pairs(
        self, store: ArtifactStore
    ) -> None:
        """Incomplete pair (mesh only + pending marker) is cleaned up."""
        mesh_path = os.path.join(store.artifact_root, "incomplete.dae")
        marker = pending_marker_for(mesh_path)

        # Simulate crash: mesh written, manifest not, marker exists
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())
        with open(marker, "w") as f:
            f.write("pending")

        stats = store.recovery_scan()
        assert stats["pending_found"] == 1
        assert stats["cleaned"] == 1
        assert not os.path.exists(mesh_path)
        assert not os.path.exists(marker)

    def test_recovery_completes_finished_pairs(
        self, store: ArtifactStore
    ) -> None:
        """Pair with both files + stale marker: just removes marker."""
        manifest = _make_applied_manifest(store)
        mesh_path = manifest.mesh_path
        m_path = manifest_path_for(mesh_path)
        marker = pending_marker_for(mesh_path)

        # Simulate crash after both files written but before marker removed
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())
        with open(m_path, "w") as f:
            json.dump(manifest.to_dict(), f)
        with open(marker, "w") as f:
            f.write("pending")

        stats = store.recovery_scan()
        assert stats["recovered"] == 1
        assert os.path.exists(mesh_path)
        assert os.path.exists(m_path)
        assert not os.path.exists(marker)
        assert store.is_committed(mesh_path)

    def test_recovery_cleans_orphan_tmp_files(
        self, store: ArtifactStore
    ) -> None:
        """Orphan .tmp files are cleaned up during recovery."""
        tmp_file = os.path.join(store.artifact_root, "orphan.dae.tmp")
        with open(tmp_file, "w") as f:
            f.write("staged")

        stats = store.recovery_scan()
        assert stats["cleaned"] >= 1
        assert not os.path.exists(tmp_file)

    def test_recovery_emits_metrics(self, store: ArtifactStore) -> None:
        """Recovery scan emits appropriate metrics."""
        metrics = get_vcad_metrics()

        # Create incomplete pair
        mesh_path = os.path.join(store.artifact_root, "incomplete.dae")
        marker = pending_marker_for(mesh_path)
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())
        with open(marker, "w") as f:
            f.write("pending")

        store.recovery_scan()

        assert metrics.get_counter("artifact_pair_incomplete_detected_total") >= 1
        assert metrics.get_counter("artifact_pair_recovery_total") >= 1

    def test_recovery_no_half_visible_artifacts(
        self, store: ArtifactStore
    ) -> None:
        """After recovery, no half-visible state remains in committed outputs."""
        # Create various incomplete states
        for i in range(3):
            mesh_path = os.path.join(store.artifact_root, f"crash-{i}.dae")
            marker = pending_marker_for(mesh_path)
            with open(mesh_path, "wb") as f:
                f.write(_make_mesh_content())
            with open(marker, "w") as f:
                f.write("pending")

        # Before recovery: nothing committed
        assert store.list_committed_artifacts() == []

        store.recovery_scan()

        # After recovery: still nothing committed (all were incomplete)
        assert store.list_committed_artifacts() == []

    def test_recovery_preserves_completed_pairs(
        self, store: ArtifactStore
    ) -> None:
        """Recovery does not remove properly committed pairs."""
        # Write a proper pair first
        manifest = _make_applied_manifest(store, node_id="good", label="good")
        store.write_artifact_pair(manifest, _make_mesh_content("good"))

        # Create an incomplete pair
        mesh_path = os.path.join(store.artifact_root, "bad.dae")
        marker = pending_marker_for(mesh_path)
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content("bad"))
        with open(marker, "w") as f:
            f.write("pending")

        store.recovery_scan()

        # Good pair still committed
        committed = store.list_committed_artifacts()
        assert any("good" in p for p in committed)
        # Bad pair cleaned
        assert not os.path.exists(mesh_path)


# ===========================================================================
# Path hardening
# ===========================================================================


class TestPathHardening:
    """Traversal/symlink manifest path attempts fail with PATH_NOT_ALLOWED."""

    def test_traversal_rejected(self, artifact_root: str) -> None:
        """Path with ../ traversal is rejected."""
        evil_path = os.path.join(artifact_root, "..", "escape.dae")
        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_artifact_path(evil_path, artifact_root)

    def test_valid_path_accepted(self, artifact_root: str) -> None:
        """Path within root is accepted."""
        good_path = os.path.join(artifact_root, "model.dae")
        result = validate_artifact_path(good_path, artifact_root)
        assert artifact_root in result

    def test_symlink_escape_rejected(self, artifact_root: str, tmp_path) -> None:
        """Symlink pointing outside root is rejected."""
        outside = str(tmp_path / "outside")
        os.makedirs(outside)

        link_path = os.path.join(artifact_root, "escape-link")
        target = os.path.join(outside, "evil.dae")
        with open(target, "w") as f:
            f.write("evil")
        os.symlink(target, link_path)

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_artifact_path(link_path, artifact_root)

    def test_store_rejects_traversal_on_write(self, store: ArtifactStore) -> None:
        """Store rejects writing manifest with traversal path."""
        evil_mesh_path = os.path.join(store.artifact_root, "..", "evil.dae")
        manifest = build_applied_manifest(
            node_id="evil",
            revision=1,
            request_id=None,
            source_file="/evil.cmp.oo",
            source_hash=compute_source_hash("evil"),
            mesh_path=evil_mesh_path,
            bbox={"min": [0, 0, 0], "max": [1, 1, 1]},
            volume=1.0,
            surface_area=6.0,
        )

        with pytest.raises(ValueError, match="escapes allowed root"):
            store.write_artifact_pair(manifest, b"evil")

    def test_diagnostics_path_escape_returns_error(
        self, store: ArtifactStore, tmp_path
    ) -> None:
        """Diagnostics reader reports PATH_NOT_ALLOWED for symlink escapes."""
        # Create a valid mesh file
        mesh_path = os.path.join(store.artifact_root, "normal.dae")
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        # Create a symlink for the manifest that points outside
        outside = str(tmp_path / "outside_manifest")
        os.makedirs(outside)
        evil_manifest = os.path.join(outside, "evil.manifest.json")
        with open(evil_manifest, "w") as f:
            json.dump({"status": "applied"}, f)

        m_link = manifest_path_for(mesh_path)
        os.symlink(evil_manifest, m_link)

        # Diagnostics should report PATH_NOT_ALLOWED
        manifests, errors = store.read_manifests_for_diagnostics()
        path_errors = [e for e in errors if e["error_code"] == "PATH_NOT_ALLOWED"]
        assert len(path_errors) >= 1


# ===========================================================================
# Committed visibility
# ===========================================================================


class TestCommittedVisibility:
    """Interrupted pair publish -> committed list remains consistent."""

    def test_only_committed_pairs_in_listing(
        self, store: ArtifactStore
    ) -> None:
        """list_committed_artifacts returns only fully committed pairs."""
        # Write one committed pair
        m1 = _make_applied_manifest(store, node_id="committed", label="c")
        store.write_artifact_pair(m1, _make_mesh_content("c"))

        # Create an incomplete pair (mesh + marker, no manifest)
        obj2 = os.path.join(store.artifact_root, "incomplete.dae")
        with open(obj2, "wb") as f:
            f.write(_make_mesh_content("incomplete"))
        with open(pending_marker_for(obj2), "w") as f:
            f.write("pending")

        committed = store.list_committed_artifacts()
        assert m1.mesh_path in committed
        assert obj2 not in committed

    def test_committed_appears_exactly_once(
        self, store: ArtifactStore
    ) -> None:
        """Once committed, artifact appears exactly once in listing."""
        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        committed = store.list_committed_artifacts()
        count = committed.count(manifest.mesh_path)
        assert count == 1

    def test_staged_tmp_files_excluded(self, store: ArtifactStore) -> None:
        """Staged .tmp files are excluded from committed listing."""
        # Write a .tmp file
        tmp_file = os.path.join(store.artifact_root, "staged.dae.tmp")
        with open(tmp_file, "w") as f:
            f.write("staged")

        committed = store.list_committed_artifacts()
        assert tmp_file not in committed

    def test_pending_marker_excluded(self, store: ArtifactStore) -> None:
        """Pending marker files are excluded from committed listing."""
        marker = os.path.join(store.artifact_root, "test.dae.pair.pending")
        with open(marker, "w") as f:
            f.write("pending")

        committed = store.list_committed_artifacts()
        assert marker not in committed

    def test_read_manifest_returns_none_for_uncommitted(
        self, store: ArtifactStore
    ) -> None:
        """read_manifest returns None for uncommitted artifacts."""
        mesh_path = os.path.join(store.artifact_root, "uncommitted.dae")
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        result = store.read_manifest(mesh_path)
        assert result is None


# ===========================================================================
# Diagnostics reader
# ===========================================================================


class TestDiagnosticsReader:
    """Prepare valid + invalid + missing manifests -> partial success + per-item errors."""

    def test_valid_manifest_included(self, store: ArtifactStore) -> None:
        """Valid committed manifests appear in diagnostics output."""
        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        manifests, errors = store.read_manifests_for_diagnostics()
        assert len(manifests) == 1
        assert manifests[0]["status"] == "applied"
        assert errors == []

    def test_invalid_schema_returns_error(self, store: ArtifactStore) -> None:
        """Invalid schema => SCHEMA_VALIDATION_FAILED."""
        mesh_path = os.path.join(store.artifact_root, "invalid.dae")
        m_path = manifest_path_for(mesh_path)

        # Write mesh
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        # Write invalid manifest (missing required fields)
        with open(m_path, "w") as f:
            json.dump({"status": "applied"}, f)  # missing source_hash, mesh_path, finished_at

        manifests, errors = store.read_manifests_for_diagnostics()
        assert len(errors) >= 1
        schema_errors = [
            e for e in errors if e["error_code"] == "SCHEMA_VALIDATION_FAILED"
        ]
        assert len(schema_errors) >= 1

    def test_missing_manifest_returns_error(self, store: ArtifactStore) -> None:
        """Missing manifest file => ARTIFACT_READ_FAILED."""
        mesh_path = os.path.join(store.artifact_root, "no-manifest.dae")
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        manifests, errors = store.read_manifests_for_diagnostics()
        read_errors = [
            e for e in errors if e["error_code"] == "ARTIFACT_READ_FAILED"
        ]
        assert len(read_errors) >= 1
        assert read_errors[0]["details"]["reason"] == "file_not_found"

    def test_corrupt_manifest_returns_error(self, store: ArtifactStore) -> None:
        """Corrupt (non-JSON) manifest file => ARTIFACT_READ_FAILED."""
        mesh_path = os.path.join(store.artifact_root, "corrupt.dae")
        m_path = manifest_path_for(mesh_path)

        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())
        with open(m_path, "w") as f:
            f.write("not valid json{{{")

        manifests, errors = store.read_manifests_for_diagnostics()
        read_errors = [
            e for e in errors if e["error_code"] == "ARTIFACT_READ_FAILED"
        ]
        assert len(read_errors) >= 1

    def test_mixed_valid_invalid_missing(self, store: ArtifactStore) -> None:
        """Mix of valid, invalid, and missing produces partial success."""
        # Valid
        m_valid = _make_applied_manifest(store, node_id="valid", label="valid")
        store.write_artifact_pair(m_valid, _make_mesh_content("valid"))

        # Invalid schema
        invalid_path = os.path.join(store.artifact_root, "invalid.dae")
        with open(invalid_path, "wb") as f:
            f.write(_make_mesh_content("invalid"))
        with open(manifest_path_for(invalid_path), "w") as f:
            json.dump({"status": "applied"}, f)

        # Missing manifest
        missing_path = os.path.join(store.artifact_root, "missing.dae")
        with open(missing_path, "wb") as f:
            f.write(_make_mesh_content("missing"))

        manifests, errors = store.read_manifests_for_diagnostics()

        # One valid manifest
        assert len(manifests) == 1
        assert manifests[0]["node_id"] == "valid"

        # Two errors (invalid + missing)
        assert len(errors) == 2

    def test_no_crash_on_malformed_manifest(self, store: ArtifactStore) -> None:
        """Processing continues even with malformed manifest files."""
        # Create multiple artifacts, some malformed
        for i in range(3):
            mesh_path = os.path.join(store.artifact_root, f"file-{i}.dae")
            m_path = manifest_path_for(mesh_path)
            with open(mesh_path, "wb") as f:
                f.write(_make_mesh_content(f"file-{i}"))
            if i == 1:
                with open(m_path, "w") as f:
                    f.write("}{bad json")
            else:
                manifest = _make_applied_manifest(
                    store, node_id=f"node-{i}", revision=i + 1, label=f"l{i}"
                )
                # Override mesh_path in the manifest dict
                d = manifest.to_dict()
                d["mesh_path"] = mesh_path
                with open(m_path, "w") as f:
                    json.dump(d, f)

        manifests, errors = store.read_manifests_for_diagnostics()
        # Should have 2 valid + 1 error
        assert len(manifests) == 2
        assert len(errors) == 1

    def test_deterministic_error_ordering(self, store: ArtifactStore) -> None:
        """manifest_read_errors sorted by (manifest_path, error_code)."""
        # Create multiple errors
        for name in ["z-missing", "a-missing", "m-missing"]:
            mesh_path = os.path.join(store.artifact_root, f"{name}.dae")
            with open(mesh_path, "wb") as f:
                f.write(_make_mesh_content())

        _manifests, errors = store.read_manifests_for_diagnostics()
        assert len(errors) == 3

        # Should be sorted by manifest_path
        paths = [e["manifest_path"] for e in errors]
        assert paths == sorted(paths)

    def test_per_item_error_payload_shape(self, store: ArtifactStore) -> None:
        """Each error has manifest_path, error_code, message, details."""
        mesh_path = os.path.join(store.artifact_root, "error-shape.dae")
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        _manifests, errors = store.read_manifests_for_diagnostics()
        assert len(errors) == 1

        error = errors[0]
        assert "manifest_path" in error
        assert "error_code" in error
        assert "message" in error
        assert "details" in error
        assert "operation" in error["details"]

    def test_in_progress_artifacts_skipped(self, store: ArtifactStore) -> None:
        """Artifacts with pending markers are skipped in diagnostics."""
        mesh_path = os.path.join(store.artifact_root, "pending.dae")
        m_path = manifest_path_for(mesh_path)
        marker = pending_marker_for(mesh_path)

        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())
        with open(m_path, "w") as f:
            json.dump(
                _make_applied_manifest(store, node_id="pending").to_dict(), f
            )
        with open(marker, "w") as f:
            f.write("pending")

        manifests, errors = store.read_manifests_for_diagnostics()
        # Should be skipped entirely (no error, no manifest)
        assert len(manifests) == 0
        assert len(errors) == 0


# ===========================================================================
# Diagnostics integration
# ===========================================================================


class TestDiagnosticsIntegration:
    """vcad_metrics returns last_artifact_manifest when available."""

    def test_vcad_metrics_includes_last_manifest(
        self, store: ArtifactStore
    ) -> None:
        """vcad_metrics includes last_artifact_manifest."""
        from supex_driver.connection.vcad_artifact_manifest import (
            _reset_artifact_store,
            get_artifact_store,
        )
        from supex_driver.mcp.vcad_diagnostics import (
            vcad_metrics as vcad_metrics_tool,
        )

        # Reset and set up store with known root
        _reset_artifact_store()

        # Write an artifact using the store directly
        manifest = build_applied_manifest(
            node_id="diag-node",
            revision=1,
            request_id="diag-req",
            source_file="/project/diag.cmp.oo",
            source_hash=compute_source_hash("[cube 1 1 1]"),
            mesh_path=os.path.join(store.artifact_root, "diag-r1.dae"),
            bbox={"min": [0, 0, 0], "max": [1, 1, 1]},
            volume=1.0,
            surface_area=6.0,
            finished_at=1700000000.0,
        )
        store.write_artifact_pair(manifest, _make_mesh_content("diag"))

        # Patch the singleton to use our store
        import supex_driver.connection.vcad_artifact_manifest as am_module

        old_store = am_module._store
        am_module._store = store
        try:
            result = vcad_metrics_tool(ctx=None)
            parsed = json.loads(result)
            assert "last_artifact_manifest" in parsed
            assert parsed["last_artifact_manifest"]["node_id"] == "diag-node"
        finally:
            am_module._store = old_store

    def test_vcad_metrics_without_artifacts(self) -> None:
        """vcad_metrics works even without any artifacts."""
        from supex_driver.mcp.vcad_diagnostics import (
            vcad_metrics as vcad_metrics_tool,
        )

        result = vcad_metrics_tool(ctx=None)
        parsed = json.loads(result)

        # Should still have all metric names
        from supex_driver.connection.vcad_metrics import METRIC_NAMES

        for name in METRIC_NAMES:
            assert name in parsed

    def test_vcad_metrics_with_manifest_errors(
        self, store: ArtifactStore
    ) -> None:
        """vcad_metrics includes manifest_read_errors when present."""
        import supex_driver.connection.vcad_artifact_manifest as am_module
        from supex_driver.mcp.vcad_diagnostics import (
            vcad_metrics as vcad_metrics_tool,
        )

        # Create a mesh without manifest
        mesh_path = os.path.join(store.artifact_root, "error-test.dae")
        with open(mesh_path, "wb") as f:
            f.write(_make_mesh_content())

        old_store = am_module._store
        am_module._store = store
        try:
            result = vcad_metrics_tool(ctx=None)
            parsed = json.loads(result)
            assert "manifest_read_errors" in parsed
            assert len(parsed["manifest_read_errors"]) >= 1
        finally:
            am_module._store = old_store


# ===========================================================================
# Compatibility
# ===========================================================================


class TestCompatibility:
    """Additive manifest fields accepted by parser/schema without protocol bump."""

    def test_additive_fields_accepted(self) -> None:
        """Manifest with extra fields passes schema validation."""
        manifest_dict = {
            "status": "applied",
            "node_id": "node-1",
            "revision": 1,
            "request_id": "req-1",
            "source_file": "/project/node-1.cmp.oo",
            "source_hash": compute_source_hash("[cube 10 10 10]"),
            "mesh_path": "/artifacts/node-1.dae",
            "finished_at": "2024-01-01T00:00:00.000Z",
            "bbox": {"min": [0, 0, 0], "max": [10, 10, 10]},
            "volume": 1000.0,
            "surface_area": 600.0,
            # Additive future fields
            "custom_future_field": "hello",
            "another_new_field": 42,
        }

        errors = validate_artifact_manifest(manifest_dict)
        assert errors == [], f"Additive fields should be accepted: {errors}"

    def test_from_dict_ignores_unknown_fields(self) -> None:
        """ArtifactManifest.from_dict ignores unknown fields."""
        d = {
            "status": "applied",
            "node_id": "node-1",
            "revision": 1,
            "request_id": "req-1",
            "source_file": "/project/node-1.cmp.oo",
            "source_hash": "abc123",
            "mesh_path": "/artifacts/node-1.dae",
            "finished_at": "2024-01-01T00:00:00.000Z",
            "future_field": "should_be_ignored",
        }

        manifest = ArtifactManifest.from_dict(d)
        assert manifest.status == "applied"
        assert manifest.node_id == "node-1"

    def test_schema_allows_additional_properties(self) -> None:
        """Schema has additionalProperties: true."""
        from supex_driver.connection.vcad_schema import load_schema

        schema = load_schema("v1", "artifact-manifest")
        assert schema.get("additionalProperties") is True

    def test_imports_metadata_in_manifest(self) -> None:
        """Import references are included in manifest."""
        imports = [
            {
                "binding_name": "dims",
                "selector": "entity:12345",
                "extracts": ["dims"],
                "resolved_type": "native",
                "source_node_id": None,
            }
        ]

        manifest_dict = {
            "status": "applied",
            "node_id": "node-1",
            "revision": 1,
            "source_hash": compute_source_hash("[cube 10 10 10]"),
            "mesh_path": "/artifacts/node-1.dae",
            "finished_at": "2024-01-01T00:00:00.000Z",
            "imports": imports,
            "bbox": {"min": [0, 0, 0], "max": [10, 10, 10]},
            "volume": 1000.0,
            "surface_area": 600.0,
        }

        errors = validate_artifact_manifest(manifest_dict)
        assert errors == [], f"Imports should validate: {errors}"

    def test_timings_in_manifest(self) -> None:
        """All timing fields validate correctly."""
        manifest_dict = {
            "status": "applied",
            "node_id": "node-1",
            "revision": 1,
            "source_hash": compute_source_hash("[cube 10 10 10]"),
            "mesh_path": "/artifacts/node-1.dae",
            "queued_at": "2024-01-01T00:00:00.000Z",
            "started_at": "2024-01-01T00:00:01.000Z",
            "finished_at": "2024-01-01T00:00:02.000Z",
            "eval_duration_ms": 1000.0,
            "bbox": {"min": [0, 0, 0], "max": [10, 10, 10]},
            "volume": 1000.0,
            "surface_area": 600.0,
        }

        errors = validate_artifact_manifest(manifest_dict)
        assert errors == [], f"Timings should validate: {errors}"


# ===========================================================================
# Observability counters
# ===========================================================================


class TestObservabilityCounters:
    """Manifest write and retention metrics are tracked correctly."""

    def test_write_increments_counter(self, store: ArtifactStore) -> None:
        """Each write increments artifact_manifests_written_total."""
        metrics = get_vcad_metrics()

        manifest = _make_applied_manifest(store)
        store.write_artifact_pair(manifest, _make_mesh_content())

        assert metrics.get_counter("artifact_manifests_written_total") == 1

    def test_retained_gauge_updated(self, store: ArtifactStore) -> None:
        """artifact_manifests_retained_current reflects committed count."""
        metrics = get_vcad_metrics()

        for i in range(3):
            m = _make_applied_manifest(
                store, node_id=f"gauge-{i}", revision=i + 1, label=f"g{i}"
            )
            store.write_artifact_pair(m, _make_mesh_content(f"gauge-{i}"))

        assert metrics.get_gauge("artifact_manifests_retained_current") == 3.0

    def test_multiple_writes_counter_monotonic(
        self, store: ArtifactStore
    ) -> None:
        """Written counter is monotonically increasing."""
        metrics = get_vcad_metrics()

        for i in range(5):
            m = _make_applied_manifest(
                store, node_id=f"mono-{i}", revision=i + 1, label=f"m{i}"
            )
            store.write_artifact_pair(m, _make_mesh_content(f"mono-{i}"))
            assert (
                metrics.get_counter("artifact_manifests_written_total")
                == i + 1
            )
