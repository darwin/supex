"""vcad runtime state management.

Handles per-node revision tracking, eval queue with supersede pruning,
trigger coalescing, persistent state, and startup recovery/reconciliation.
"""

import contextlib
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("supex.vcad.state")

# Environment variable defaults
VCAD_STATE_PATH_ENV = "VCAD_STATE_PATH"
VCAD_MAX_QUEUE = int(os.environ.get("VCAD_MAX_QUEUE", "64"))
VCAD_TRIGGER_COALESCE_MS = float(os.environ.get("VCAD_TRIGGER_COALESCE_MS", "150"))


@dataclass
class NodeState:
    """Persisted per-node vcad runtime state."""

    node_id: str
    source_file: str
    revision: int = 0
    applied_revision: int = 0
    last_entity_id: str | None = None
    status: str = "active"  # active, degraded, orphan


class RevisionTracker:
    """Per-node monotonic revision counters with stale-result protection.

    Every eval/update task carries {node_id, revision} metadata.
    The driver applies geometry only when revision == current_revision(node_id).
    Late results for older revisions are dropped.
    """

    def __init__(self) -> None:
        self._revisions: dict[str, int] = {}
        self._lock = threading.Lock()
        self.stale_dropped: int = 0

    def current_revision(self, node_id: str) -> int:
        """Get the current revision for a node."""
        with self._lock:
            return self._revisions.get(node_id, 0)

    def next_revision(self, node_id: str) -> int:
        """Increment and return the new revision for a node."""
        with self._lock:
            rev = self._revisions.get(node_id, 0) + 1
            self._revisions[node_id] = rev
            return rev

    def should_apply(self, node_id: str, revision: int) -> bool:
        """Check if a result should be applied (not stale).

        Returns True only if revision matches the current revision.
        Increments stale_dropped counter on mismatch.
        """
        with self._lock:
            current = self._revisions.get(node_id, 0)
            if revision == current:
                return True
            self.stale_dropped += 1
            logger.debug(
                f"Stale result dropped for {node_id}: "
                f"result_rev={revision}, current_rev={current}"
            )
            return False

    def set_revision(self, node_id: str, revision: int) -> None:
        """Set revision for a node (used during state reconstruction)."""
        with self._lock:
            self._revisions[node_id] = revision

    def remove_node(self, node_id: str) -> None:
        """Remove tracking for a node."""
        with self._lock:
            self._revisions.pop(node_id, None)


@dataclass
class EvalJob:
    """A queued evaluation job."""

    node_id: str
    revision: int
    source: str  # code string or file path
    job_type: str = "eval_code"  # eval_code, eval_file
    superseded: bool = False
    created_at: float = field(default_factory=time.time)


class EvalQueue:
    """Supersede-aware bounded evaluation queue.

    When a new eval job for node_id is enqueued, older pending (not-yet-started)
    jobs for the same node_id are marked as superseded. The eval worker checks
    supersede status immediately before starting compute; superseded jobs are
    skipped without evaluation.
    """

    def __init__(self, max_size: int = VCAD_MAX_QUEUE):
        self.max_size = max_size
        self._queue: list[EvalJob] = []
        self._lock = threading.Lock()
        self.superseded_dropped_total: int = 0
        self.superseded_skipped_before_eval_total: int = 0

    def enqueue(self, job: EvalJob) -> bool:
        """Add an eval job to the queue.

        Marks older pending jobs for the same node as superseded.

        Args:
            job: The eval job to enqueue.

        Returns:
            True if enqueued, False if queue is full.
        """
        with self._lock:
            if len(self._queue) >= self.max_size:
                return False
            # Mark older pending jobs for same node as superseded
            for existing in self._queue:
                if existing.node_id == job.node_id and not existing.superseded:
                    existing.superseded = True
                    self.superseded_dropped_total += 1
            self._queue.append(job)
            return True

    def get_next(self) -> EvalJob | None:
        """Get the next non-superseded job from the queue.

        Superseded jobs are skipped and counted.

        Returns:
            The next job to evaluate, or None if queue is empty.
        """
        with self._lock:
            while self._queue:
                job = self._queue.pop(0)
                if job.superseded:
                    self.superseded_skipped_before_eval_total += 1
                    continue
                return job
            return None

    def pending_count(self) -> int:
        """Number of pending (non-superseded) jobs in queue."""
        with self._lock:
            return sum(1 for j in self._queue if not j.superseded)

    def clear(self) -> None:
        """Clear all pending jobs."""
        with self._lock:
            self._queue.clear()


class TriggerCoalescer:
    """Coalesces rapid change events within a time window.

    Merges rapid change events from fs-watch, mod-track, su-observer,
    and manual updates into one pending node set. Exactly one topological
    cascade is scheduled per coalesced batch. Events arriving during an
    active cascade are queued for the next batch.

    Args:
        coalesce_ms: Coalescing window in milliseconds.
        callback: Function called with the set of affected node_ids.
    """

    def __init__(
        self,
        coalesce_ms: float = VCAD_TRIGGER_COALESCE_MS,
        callback: Callable[[set[str]], None] | None = None,
    ):
        self.coalesce_ms = coalesce_ms
        self.callback = callback
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._cascade_active: bool = False
        self._deferred: set[str] = set()
        self.cascade_count: int = 0

    def trigger(self, node_id: str, source: str = "") -> None:
        """Register a change event for a node.

        Events within the coalescing window are merged. Events during
        an active cascade are deferred to the next batch.

        Args:
            node_id: The affected node identifier.
            source: Event source (fs-watch, mod-track, su-observer, manual).
        """
        with self._lock:
            if self._cascade_active:
                self._deferred.add(node_id)
                return
            self._pending.add(node_id)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                self.coalesce_ms / 1000.0,
                self._fire,
            )
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        """Execute the coalesced cascade callback."""
        with self._lock:
            nodes = self._pending.copy()
            self._pending.clear()
            self._timer = None
            self._cascade_active = True

        if self.callback and nodes:
            try:
                self.callback(nodes)
            except Exception as e:
                logger.error(f"Trigger cascade callback error: {e}")

        with self._lock:
            self._cascade_active = False
            self.cascade_count += 1
            if self._deferred:
                self._pending.update(self._deferred)
                self._deferred.clear()
                if self._pending:
                    self._timer = threading.Timer(
                        self.coalesce_ms / 1000.0,
                        self._fire,
                    )
                    self._timer.daemon = True
                    self._timer.start()

    def cancel(self) -> None:
        """Cancel any pending timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class VCADPersistentState:
    """Manages persistent vcad runtime state on disk.

    State is stored at ``<workspace>/.supex/vcad-state.json``.
    Writes are atomic (temp file + rename) to avoid partial state on crash.
    """

    def __init__(self, state_path: str | None = None, workspace: str | None = None):
        if state_path:
            self.state_path = state_path
        elif os.environ.get(VCAD_STATE_PATH_ENV):
            self.state_path = os.environ[VCAD_STATE_PATH_ENV]
        elif workspace:
            self.state_path = os.path.join(workspace, ".supex", "vcad-state.json")
        else:
            self.state_path = os.path.join(".supex", "vcad-state.json")

        self._nodes: dict[str, NodeState] = {}
        self._lock = threading.Lock()

    def get_node(self, node_id: str) -> NodeState | None:
        """Get state for a specific node."""
        with self._lock:
            return self._nodes.get(node_id)

    def set_node(self, state: NodeState) -> None:
        """Set state for a node."""
        with self._lock:
            self._nodes[state.node_id] = state

    def remove_node(self, node_id: str) -> None:
        """Remove a node from state."""
        with self._lock:
            self._nodes.pop(node_id, None)

    def all_nodes(self) -> dict[str, NodeState]:
        """Get a copy of all node states."""
        with self._lock:
            return dict(self._nodes)

    def save(self) -> None:
        """Atomically save state to disk (temp file + rename)."""
        with self._lock:
            data = {
                "nodes": {
                    nid: {
                        "node_id": ns.node_id,
                        "source_file": ns.source_file,
                        "revision": ns.revision,
                        "applied_revision": ns.applied_revision,
                        "last_entity_id": ns.last_entity_id,
                        "status": ns.status,
                    }
                    for nid, ns in self._nodes.items()
                }
            }

        dir_path = os.path.dirname(self.state_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=dir_path or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.state_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise

    def load(self) -> bool:
        """Load state from disk.

        Returns:
            True if state was loaded successfully, False if file not found.
        """
        if not os.path.exists(self.state_path):
            return False

        with open(self.state_path) as f:
            data = json.load(f)

        with self._lock:
            self._nodes = {}
            for nid, ns_data in data.get("nodes", {}).items():
                self._nodes[nid] = NodeState(**ns_data)

        return True


@dataclass
class DriftEntry:
    """A single drift classification entry."""

    node_id: str
    drift_type: str  # missing_node, orphan_definition, revision_gap, source_missing
    details: dict[str, Any] = field(default_factory=dict)


class VCADReconciler:
    """Handles startup recovery and state reconciliation.

    Compares persisted state with authoritative SketchUp model state
    (from list_vcad_nodes) and classifies drift for resolution.
    """

    @staticmethod
    def classify_drift(
        persisted_nodes: dict[str, NodeState],
        runtime_nodes: list[dict[str, Any]],
    ) -> list[DriftEntry]:
        """Compare persisted state with runtime state and classify drift.

        Args:
            persisted_nodes: Nodes from persisted state file.
            runtime_nodes: Nodes from SketchUp bridge list_vcad_nodes.
                Each dict has at least 'node_id' key.

        Returns:
            List of drift entries describing mismatches.
        """
        drift: list[DriftEntry] = []
        runtime_ids = {n["node_id"] for n in runtime_nodes}
        persisted_ids = set(persisted_nodes.keys())

        for nid, ns in persisted_nodes.items():
            if nid not in runtime_ids:
                drift.append(DriftEntry(nid, "missing_node"))
            elif not os.path.exists(ns.source_file):
                drift.append(
                    DriftEntry(nid, "source_missing", {"source_file": ns.source_file})
                )
            elif ns.applied_revision < ns.revision:
                drift.append(
                    DriftEntry(
                        nid,
                        "revision_gap",
                        {
                            "revision": ns.revision,
                            "applied_revision": ns.applied_revision,
                        },
                    )
                )

        for rn in runtime_nodes:
            if rn["node_id"] not in persisted_ids:
                drift.append(DriftEntry(rn["node_id"], "orphan_definition"))

        return drift

    @staticmethod
    def reconcile(
        state: VCADPersistentState,
        drift: list[DriftEntry],
    ) -> dict[str, Any]:
        """Apply reconciliation policy based on drift entries.

        Returns:
            Status dict with actions taken and any errors:
            - status: "ok" | "reconciled" | "degraded"
            - actions: list of {node_id, action, ...}
            - drift: list of {node_id, type, ...}
        """
        if not drift:
            return {"status": "ok", "action": "none"}

        result: dict[str, Any] = {"status": "reconciled", "actions": [], "drift": []}

        for d in drift:
            result["drift"].append(
                {"node_id": d.node_id, "type": d.drift_type, **d.details}
            )

            if d.drift_type == "source_missing":
                node = state.get_node(d.node_id)
                if node:
                    node.status = "degraded"
                    state.set_node(node)
                result["actions"].append(
                    {
                        "node_id": d.node_id,
                        "action": "mark_degraded",
                        "error_code": "SOURCE_FILE_MISSING",
                    }
                )

            elif d.drift_type == "orphan_definition":
                state.set_node(
                    NodeState(
                        node_id=d.node_id,
                        source_file="",
                        status="orphan",
                    )
                )
                result["actions"].append(
                    {"node_id": d.node_id, "action": "mark_orphan"}
                )

            elif d.drift_type == "revision_gap":
                result["actions"].append(
                    {"node_id": d.node_id, "action": "cascade_update"}
                )

            elif d.drift_type == "missing_node":
                state.remove_node(d.node_id)
                result["actions"].append(
                    {"node_id": d.node_id, "action": "remove_persisted"}
                )

        # Check if all issues are unrecoverable
        source_missing = [d for d in drift if d.drift_type == "source_missing"]
        if source_missing:
            result["status"] = "degraded"

        return result

    @staticmethod
    def rebuild_revisions(
        state: VCADPersistentState,
        tracker: RevisionTracker,
    ) -> None:
        """Reconstruct revision counters from persisted state.

        Used during startup recovery to restore in-memory tracking
        from the last known persisted state.
        """
        for nid, ns in state.all_nodes().items():
            tracker.set_revision(nid, ns.revision)
