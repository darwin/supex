"""VCAD artifact manifest: deterministic eval artifacts with committed visibility.

Handles writing, reading, retention, and crash recovery for eval artifact
pairs (mesh file + manifest JSON). An artifact is "committed" only when both
files exist and no pending marker is present.

Path policy: manifest paths are derived internally from accepted mesh_path;
traversal and symlink escapes are rejected with PATH_NOT_ALLOWED.
"""

import contextlib
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from supex_driver.connection.vcad_exceptions import PATH_NOT_ALLOWED

logger = logging.getLogger("supex.vcad.artifact")

# Marker extension for in-progress pair publish
PAIR_PENDING_EXT = ".pair.pending"
MANIFEST_EXT = ".manifest.json"
TMP_SUFFIX = ".tmp"


def _rfc3339_utc(ts: float | None = None) -> str:
    """Format a Unix timestamp (or now) as RFC3339 UTC."""
    if ts is None:
        ts = time.time()
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "." + f"{dt.microsecond:06d}"[
        :3
    ] + "Z"


def compute_source_hash(source: str) -> str:
    """Compute a deterministic SHA-256 hash of canonicalized source."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def manifest_path_for(mesh_path: str) -> str:
    """Derive the manifest path from an mesh_path (mesh artifact path)."""
    return mesh_path + MANIFEST_EXT


def pending_marker_for(mesh_path: str) -> str:
    """Derive the pending pair marker path from an mesh_path."""
    return mesh_path + PAIR_PENDING_EXT


def _canonical_real_path(path: str) -> str:
    """Resolve a path to its real canonical form (following symlinks)."""
    return os.path.realpath(os.path.normpath(path))


def validate_artifact_path(path: str, allowed_root: str) -> str:
    """Validate and canonicalize an artifact path under the allowed root.

    Rejects traversal (../) and symlink escapes.

    Args:
        path: The path to validate.
        allowed_root: The workspace-scoped allowed root directory.

    Returns:
        Canonicalized path.

    Raises:
        ValueError: If path escapes the allowed root.
    """
    canon = _canonical_real_path(path)
    root = _canonical_real_path(allowed_root)

    if not canon.startswith(root + os.sep) and canon != root:
        raise ValueError(f"Path escapes allowed root: {path}")

    return canon


@dataclass
class ArtifactManifest:
    """A single eval artifact manifest."""

    status: str  # applied, stale_dropped, superseded
    node_id: str
    revision: int
    request_id: str | None
    source_file: str
    source_hash: str
    mesh_path: str
    finished_at: str  # RFC3339 UTC

    # Optional fields depending on status
    imports: list[dict[str, Any]] = field(default_factory=list)
    bbox: dict[str, list[float]] | None = None
    volume: float | None = None
    surface_area: float | None = None
    queued_at: str | None = None
    started_at: str | None = None
    eval_duration_ms: float | None = None

    # Terminal status fields
    drop_reason: str | None = None
    supersede_reason: str | None = None
    superseded_by_revision: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict with canonical field ordering."""
        d: dict[str, Any] = {}

        # Canonical field order
        d["status"] = self.status
        d["node_id"] = self.node_id
        d["revision"] = self.revision
        d["request_id"] = self.request_id
        d["source_file"] = self.source_file
        d["source_hash"] = self.source_hash
        if self.imports:
            d["imports"] = self.imports
        d["mesh_path"] = self.mesh_path

        if self.bbox is not None:
            d["bbox"] = self.bbox
        if self.volume is not None:
            d["volume"] = self.volume
        if self.surface_area is not None:
            d["surface_area"] = self.surface_area

        if self.queued_at is not None:
            d["queued_at"] = self.queued_at
        if self.started_at is not None:
            d["started_at"] = self.started_at
        d["finished_at"] = self.finished_at
        if self.eval_duration_ms is not None:
            d["eval_duration_ms"] = self.eval_duration_ms

        if self.drop_reason is not None:
            d["drop_reason"] = self.drop_reason
        if self.supersede_reason is not None:
            d["supersede_reason"] = self.supersede_reason
        if self.superseded_by_revision is not None:
            d["superseded_by_revision"] = self.superseded_by_revision

        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArtifactManifest":
        """Deserialize from dict."""
        return cls(
            status=d["status"],
            node_id=d.get("node_id", ""),
            revision=d.get("revision", 0),
            request_id=d.get("request_id"),
            source_file=d.get("source_file", ""),
            source_hash=d["source_hash"],
            mesh_path=d["mesh_path"],
            finished_at=d["finished_at"],
            imports=d.get("imports", []),
            bbox=d.get("bbox"),
            volume=d.get("volume"),
            surface_area=d.get("surface_area"),
            queued_at=d.get("queued_at"),
            started_at=d.get("started_at"),
            eval_duration_ms=d.get("eval_duration_ms"),
            drop_reason=d.get("drop_reason"),
            supersede_reason=d.get("supersede_reason"),
            superseded_by_revision=d.get("superseded_by_revision"),
        )


def build_applied_manifest(
    *,
    node_id: str,
    revision: int,
    request_id: str | None,
    source_file: str,
    source_hash: str,
    mesh_path: str,
    imports: list[dict[str, Any]] | None = None,
    bbox: dict[str, list[float]] | None = None,
    volume: float | None = None,
    surface_area: float | None = None,
    queued_at: float | None = None,
    started_at: float | None = None,
    finished_at: float | None = None,
    eval_duration_ms: float | None = None,
) -> ArtifactManifest:
    """Build an applied artifact manifest."""
    return ArtifactManifest(
        status="applied",
        node_id=node_id,
        revision=revision,
        request_id=request_id,
        source_file=source_file,
        source_hash=source_hash,
        mesh_path=mesh_path,
        imports=imports or [],
        bbox=bbox,
        volume=volume,
        surface_area=surface_area,
        queued_at=_rfc3339_utc(queued_at) if queued_at else None,
        started_at=_rfc3339_utc(started_at) if started_at else None,
        finished_at=_rfc3339_utc(finished_at),
        eval_duration_ms=eval_duration_ms,
    )


def build_stale_dropped_manifest(
    *,
    node_id: str,
    revision: int,
    request_id: str | None,
    source_file: str,
    source_hash: str,
    mesh_path: str,
    drop_reason: str,
    finished_at: float | None = None,
) -> ArtifactManifest:
    """Build a stale_dropped artifact manifest."""
    return ArtifactManifest(
        status="stale_dropped",
        node_id=node_id,
        revision=revision,
        request_id=request_id,
        source_file=source_file,
        source_hash=source_hash,
        mesh_path=mesh_path,
        finished_at=_rfc3339_utc(finished_at),
        drop_reason=drop_reason,
    )


def build_superseded_manifest(
    *,
    node_id: str,
    revision: int,
    request_id: str | None,
    source_file: str,
    source_hash: str,
    mesh_path: str,
    supersede_reason: str,
    superseded_by_revision: int | None = None,
    finished_at: float | None = None,
) -> ArtifactManifest:
    """Build a superseded artifact manifest."""
    return ArtifactManifest(
        status="superseded",
        node_id=node_id,
        revision=revision,
        request_id=request_id,
        source_file=source_file,
        source_hash=source_hash,
        mesh_path=mesh_path,
        finished_at=_rfc3339_utc(finished_at),
        supersede_reason=supersede_reason,
        superseded_by_revision=superseded_by_revision,
    )


class ArtifactStore:
    """Manages artifact pairs (mesh + manifest) with atomic commit and recovery.

    Artifacts are stored under a workspace-scoped root directory.
    Each artifact pair consists of a mesh file (*.dae) and its manifest
    (*.dae.manifest.json).

    Committed visibility: an artifact is committed only when both files
    exist and no pending marker is present.

    Thread-safe for concurrent writes.
    """

    def __init__(self, artifact_root: str, max_retained: int = 100) -> None:
        self.artifact_root = artifact_root
        self.max_retained = max_retained
        self._lock = threading.Lock()

        os.makedirs(artifact_root, exist_ok=True)

    def _validate_path(self, path: str) -> str:
        """Validate that a path is under the artifact root."""
        return validate_artifact_path(path, self.artifact_root)

    def write_artifact_pair(
        self,
        manifest: ArtifactManifest,
        mesh_content: bytes | None = None,
    ) -> str:
        """Atomically write a mesh + manifest artifact pair.

        Steps:
        1. Write staged files (*.tmp)
        2. Create pending marker
        3. Rename staged files to final paths
        4. Remove pending marker

        Args:
            manifest: The artifact manifest.
            mesh_content: Optional mesh file content (if None, mesh file
                is expected to exist already at mesh_path).

        Returns:
            The manifest path.
        """
        mesh_path = manifest.mesh_path
        m_path = manifest_path_for(mesh_path)
        marker_path = pending_marker_for(mesh_path)

        # Validate paths
        self._validate_path(mesh_path)
        self._validate_path(m_path)

        mesh_dir = os.path.dirname(mesh_path)
        os.makedirs(mesh_dir, exist_ok=True)

        manifest_data = json.dumps(
            manifest.to_dict(), indent=2, sort_keys=False
        )

        with self._lock:
            # Stage files
            mesh_tmp = mesh_path + TMP_SUFFIX
            manifest_tmp = m_path + TMP_SUFFIX

            try:
                # Write staged mesh
                if mesh_content is not None:
                    with open(mesh_tmp, "wb") as f:
                        f.write(mesh_content)

                # Write staged manifest
                with open(manifest_tmp, "w") as f:
                    f.write(manifest_data)

                # Create pending marker
                with open(marker_path, "w") as f:
                    f.write(str(time.time()))

                # Publish: rename staged files
                if mesh_content is not None:
                    os.replace(mesh_tmp, mesh_path)
                os.replace(manifest_tmp, m_path)

                # Remove pending marker (commit complete)
                with contextlib.suppress(OSError):
                    os.unlink(marker_path)

                # Emit metrics
                self._emit_write_metrics()

            except Exception:
                # Cleanup staged files on failure
                for p in (mesh_tmp, manifest_tmp, marker_path):
                    with contextlib.suppress(OSError):
                        os.unlink(p)
                raise

        # Retention cleanup
        self._enforce_retention()

        return m_path

    def is_committed(self, mesh_path: str) -> bool:
        """Check if an artifact pair is committed (fully visible).

        Committed = mesh exists + manifest exists + no pending marker.
        """
        m_path = manifest_path_for(mesh_path)
        marker_path = pending_marker_for(mesh_path)

        return (
            os.path.exists(mesh_path)
            and os.path.exists(m_path)
            and not os.path.exists(marker_path)
        )

    def list_committed_artifacts(self) -> list[str]:
        """List all committed artifact mesh_paths under the root.

        Returns:
            Sorted list of mesh_paths that have committed pairs.
        """
        committed = []
        if not os.path.isdir(self.artifact_root):
            return committed

        for fname in sorted(os.listdir(self.artifact_root)):
            fpath = os.path.join(self.artifact_root, fname)
            if not os.path.isfile(fpath):
                continue
            # Skip manifest, marker, and tmp files
            if (
                fname.endswith(MANIFEST_EXT)
                or fname.endswith(PAIR_PENDING_EXT)
                or fname.endswith(TMP_SUFFIX)
            ):
                continue
            if self.is_committed(fpath):
                committed.append(fpath)

        return committed

    def read_manifest(self, mesh_path: str) -> ArtifactManifest | None:
        """Read and parse a committed artifact manifest.

        Returns None if the artifact is not committed.
        """
        if not self.is_committed(mesh_path):
            return None

        m_path = manifest_path_for(mesh_path)
        try:
            with open(m_path) as f:
                data = json.load(f)
            return ArtifactManifest.from_dict(data)
        except Exception:
            return None

    def get_last_artifact_manifest(self) -> dict[str, Any] | None:
        """Get the most recent committed artifact manifest as dict.

        Returns None if no committed artifacts exist.
        """
        committed = self.list_committed_artifacts()
        if not committed:
            return None

        # Sort by mtime, most recent last
        committed.sort(key=lambda p: os.path.getmtime(p))
        last_obj = committed[-1]
        m_path = manifest_path_for(last_obj)

        try:
            self._validate_path(m_path)
            with open(m_path) as f:
                return json.load(f)
        except Exception:
            return None

    def remove_artifact_pair(self, mesh_path: str) -> None:
        """Remove a mesh + manifest pair together."""
        m_path = manifest_path_for(mesh_path)
        marker_path = pending_marker_for(mesh_path)

        for p in (mesh_path, m_path, marker_path):
            with contextlib.suppress(OSError):
                os.unlink(p)

    def recovery_scan(self) -> dict[str, int]:
        """Scan for and clean up incomplete artifact pairs on startup.

        Detects pending markers and removes incomplete staged/half-published
        artifacts. Increments recovery counters.

        Returns:
            Dict with recovery stats: pending_found, cleaned, recovered.
        """
        stats = {"pending_found": 0, "cleaned": 0, "recovered": 0}

        if not os.path.isdir(self.artifact_root):
            return stats

        # Find all pending markers
        pending_markers = []
        for fname in os.listdir(self.artifact_root):
            if fname.endswith(PAIR_PENDING_EXT):
                pending_markers.append(
                    os.path.join(self.artifact_root, fname)
                )

        stats["pending_found"] = len(pending_markers)

        for marker_path in pending_markers:
            # Derive mesh_path from marker
            mesh_path = marker_path[: -len(PAIR_PENDING_EXT)]
            m_path = manifest_path_for(mesh_path)

            # Check what state the pair is in
            has_mesh = os.path.exists(mesh_path)
            has_manifest = os.path.exists(m_path)

            if has_mesh and has_manifest:
                # Both files made it — just remove the stale marker
                with contextlib.suppress(OSError):
                    os.unlink(marker_path)
                stats["recovered"] += 1
            else:
                # Incomplete — remove all artifacts for this pair
                for p in (mesh_path, m_path, marker_path):
                    with contextlib.suppress(OSError):
                        os.unlink(p)
                stats["cleaned"] += 1

        # Clean up orphan .tmp files
        for fname in os.listdir(self.artifact_root):
            if fname.endswith(TMP_SUFFIX):
                with contextlib.suppress(OSError):
                    os.unlink(os.path.join(self.artifact_root, fname))
                stats["cleaned"] += 1

        # Emit metrics
        self._emit_recovery_metrics(stats)

        return stats

    def read_manifests_for_diagnostics(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Read all committed manifests with best-effort error handling.

        Valid manifests contribute normal data. Invalid/missing/unreadable
        manifests append per-item errors. Staged files and pending markers
        are skipped.

        Returns:
            Tuple of (manifests, manifest_read_errors).
            Errors are sorted by (manifest_path, error_code).
        """
        from supex_driver.connection.vcad_schema import validate_artifact_manifest

        manifests: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        if not os.path.isdir(self.artifact_root):
            return manifests, errors

        for fname in sorted(os.listdir(self.artifact_root)):
            fpath = os.path.join(self.artifact_root, fname)

            # Skip non-mesh files
            if (
                fname.endswith(MANIFEST_EXT)
                or fname.endswith(PAIR_PENDING_EXT)
                or fname.endswith(TMP_SUFFIX)
                or not os.path.isfile(fpath)
            ):
                continue

            m_path = manifest_path_for(fpath)
            marker_path = pending_marker_for(fpath)

            # Skip in-progress artifacts
            if os.path.exists(marker_path):
                continue

            # Path validation
            try:
                self._validate_path(m_path)
            except ValueError:
                errors.append({
                    "manifest_path": m_path,
                    "error_code": PATH_NOT_ALLOWED,
                    "message": f"Manifest path escapes allowed root",
                    "details": {
                        "operation": "read_manifest",
                        "path": m_path,
                    },
                })
                continue

            # Read manifest
            if not os.path.exists(m_path):
                errors.append({
                    "manifest_path": m_path,
                    "error_code": "ARTIFACT_READ_FAILED",
                    "message": f"Manifest file not found",
                    "details": {
                        "operation": "read_manifest",
                        "reason": "file_not_found",
                    },
                })
                continue

            try:
                with open(m_path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                errors.append({
                    "manifest_path": m_path,
                    "error_code": "ARTIFACT_READ_FAILED",
                    "message": f"Failed to read manifest: {e}",
                    "details": {
                        "operation": "read_manifest",
                        "reason": str(e),
                    },
                })
                continue

            # Schema validation
            validation_errors = validate_artifact_manifest(data)
            if validation_errors:
                errors.append({
                    "manifest_path": m_path,
                    "error_code": "SCHEMA_VALIDATION_FAILED",
                    "message": "Manifest failed schema validation",
                    "details": {
                        "operation": "read_manifest",
                        "validation_errors": validation_errors,
                    },
                })
                continue

            manifests.append(data)

        # Deterministic ordering for errors
        errors.sort(key=lambda e: (e["manifest_path"], e["error_code"]))

        return manifests, errors

    def _enforce_retention(self) -> None:
        """Enforce max_retained limit on committed artifacts.

        Removes oldest committed pairs first.
        """
        committed = self.list_committed_artifacts()
        if len(committed) <= self.max_retained:
            self._update_retained_gauge(len(committed))
            return

        # Sort by mtime, oldest first
        committed.sort(key=lambda p: os.path.getmtime(p))
        to_remove = len(committed) - self.max_retained

        for mesh_path in committed[:to_remove]:
            self.remove_artifact_pair(mesh_path)

        self._update_retained_gauge(self.max_retained)

    def _update_retained_gauge(self, count: int) -> None:
        """Update the artifact_manifests_retained_current gauge."""
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            get_vcad_metrics().set_gauge(
                "artifact_manifests_retained_current", float(count)
            )
        except Exception:
            pass

    def _emit_write_metrics(self) -> None:
        """Emit metrics after a successful artifact write."""
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            get_vcad_metrics().increment("artifact_manifests_written_total")
        except Exception:
            pass

    def _emit_recovery_metrics(self, stats: dict[str, int]) -> None:
        """Emit metrics from recovery scan."""
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            metrics = get_vcad_metrics()
            if stats["pending_found"] > 0:
                metrics.increment(
                    "artifact_pair_incomplete_detected_total",
                    stats["pending_found"],
                )
            if stats["recovered"] + stats["cleaned"] > 0:
                metrics.increment(
                    "artifact_pair_recovery_total",
                    stats["recovered"] + stats["cleaned"],
                )
        except Exception:
            pass


# Module-level singleton
_store_lock = threading.Lock()
_store: ArtifactStore | None = None


def get_artifact_store(artifact_root: str | None = None) -> ArtifactStore:
    """Get or create the global ArtifactStore singleton."""
    global _store
    with _store_lock:
        if _store is None:
            if artifact_root is None:
                workspace = os.environ.get("SUPEX_WORKSPACE")
                if workspace:
                    artifact_root = os.path.join(workspace, ".supex", "artifacts")
                else:
                    artifact_root = os.path.join(".supex", "artifacts")
            _store = ArtifactStore(artifact_root)
        return _store


def _reset_artifact_store() -> None:
    """Reset the global artifact store (for testing)."""
    global _store
    with _store_lock:
        _store = None
