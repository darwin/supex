"""VCAD runtime state management.

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
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("supex.vcad.state")

# Environment variable defaults
VCAD_STATE_PATH_ENV = "SUPEX_VCAD_STATE_PATH"
VCAD_MAX_QUEUE = int(os.environ.get("SUPEX_VCAD_MAX_QUEUE", "64"))
VCAD_TRIGGER_COALESCE_MS = float(os.environ.get("SUPEX_VCAD_TRIGGER_COALESCE_MS", "150"))


@dataclass
class NodeState:
    """Persisted per-node VCAD runtime state."""

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
        self._metrics_callback: Callable[[str, str | None], None] | None = None

    def set_metrics_callback(
        self,
        callback: Callable[[str, str | None], None],
    ) -> None:
        """Set callback for metrics emission on stale drops.

        Args:
            callback: Called with (event_name, node_id) on each stale drop.
        """
        self._metrics_callback = callback

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
            if self._metrics_callback:
                self._metrics_callback("stale_dropped", node_id)
            # Emit to centralized metrics
            try:
                from supex_driver.connection.vcad_metrics import get_vcad_metrics

                get_vcad_metrics().increment("stale_dropped_total")
            except Exception:
                pass
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
    """A queued evaluation job.

    Attributes:
        job_id: Unique job identifier (auto-generated UUID).
        node_id: Target VCAD node.
        revision: Expected revision number (stale-result protection).
        source: Code string or file path.
        job_type: "eval_code" or "eval_file".
        state: Job lifecycle state: pending, running, done, superseded.
        created_at: Timestamp of job creation.
    """

    node_id: str
    revision: int
    source: str  # code string or file path
    job_type: str = "eval_code"  # eval_code, eval_file
    state: str = "pending"  # pending, running, done, superseded
    created_at: float = field(default_factory=time.time)
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def superseded(self) -> bool:
        """Backward-compatible property: True when state is 'superseded'."""
        return self.state == "superseded"


class EvalQueue:
    """Supersede-aware bounded evaluation queue.

    When a new eval job for node_id is enqueued, older pending (not-yet-started)
    jobs for the same node_id are marked as superseded. The eval worker checks
    supersede status immediately before starting compute; superseded jobs are
    skipped without evaluation.

    Running jobs are never cancelled; their results still pass through the
    stale-result guard (RevisionTracker.should_apply) before being applied.
    """

    def __init__(self, max_size: int = VCAD_MAX_QUEUE):
        self.max_size = max_size
        self._queue: list[EvalJob] = []
        self._lock = threading.Lock()
        self.superseded_dropped_total: int = 0
        self.superseded_skipped_before_eval_total: int = 0
        self.queue_rejected_total: int = 0

    @staticmethod
    def _emit_metric(name: str) -> None:
        """Emit a metric increment to the centralized registry."""
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            get_vcad_metrics().increment(name)
        except Exception:
            pass

    @staticmethod
    def _emit_supersede_log(
        event: str,
        job: EvalJob,
        *,
        superseded_job: EvalJob | None = None,
    ) -> None:
        """Emit structured log for a queue-pruning event."""
        try:
            from supex_driver.connection.vcad_logging import emit_event

            extra: dict[str, Any] = {
                "job_id": job.job_id,
                "revision": job.revision,
            }
            if superseded_job is not None:
                extra["superseded_job_id"] = superseded_job.job_id
                extra["superseded_revision"] = superseded_job.revision
            emit_event(event, node_id=job.node_id, **extra)
        except Exception:
            pass

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
                self.queue_rejected_total += 1
                self._emit_metric("queue_rejected_total")
                return False
            # Mark older pending jobs for same node as superseded
            for existing in self._queue:
                if existing.node_id == job.node_id and existing.state == "pending":
                    existing.state = "superseded"
                    self.superseded_dropped_total += 1
                    self._emit_metric("superseded_dropped_total")
                    self._emit_supersede_log(
                        "eval_superseded_on_enqueue",
                        job,
                        superseded_job=existing,
                    )
            job.state = "pending"
            self._queue.append(job)
            return True

    def get_next(self) -> EvalJob | None:
        """Get the next non-superseded job from the queue.

        Superseded jobs are skipped and counted. The returned job is
        transitioned to 'running' state.

        Returns:
            The next job to evaluate, or None if queue is empty.
        """
        with self._lock:
            while self._queue:
                job = self._queue.pop(0)
                if job.state == "superseded":
                    self.superseded_skipped_before_eval_total += 1
                    self._emit_metric("superseded_skipped_before_eval_total")
                    self._emit_supersede_log(
                        "eval_superseded_skipped",
                        job,
                    )
                    continue
                job.state = "running"
                return job
            return None

    def pending_count(self) -> int:
        """Number of pending (non-superseded) jobs in queue."""
        with self._lock:
            return sum(1 for j in self._queue if j.state == "pending")

    def clear(self) -> None:
        """Clear all pending jobs."""
        with self._lock:
            self._queue.clear()

    def enqueue_cascade_batch(
        self,
        jobs: list[EvalJob],
        topo_order: list[str],
    ) -> list[EvalJob]:
        """Enqueue a topological cascade batch with per-node pruning.

        For each node_id in the batch, only the latest-revision job is kept;
        older revisions are marked superseded. Inter-node ordering follows
        the provided topological order so that dependencies evaluate first.

        Args:
            jobs: List of eval jobs to enqueue (may contain multiple jobs
                per node from overlapping cascade triggers).
            topo_order: Node IDs in topological dependency order
                (dependencies first).

        Returns:
            List of jobs actually enqueued (one per node, in topo order).
        """
        # Group by node_id, keep only latest revision per node
        best: dict[str, EvalJob] = {}
        superseded_in_batch: list[EvalJob] = []
        for job in jobs:
            existing = best.get(job.node_id)
            if existing is not None:
                if job.revision > existing.revision:
                    existing.state = "superseded"
                    superseded_in_batch.append(existing)
                    best[job.node_id] = job
                else:
                    job.state = "superseded"
                    superseded_in_batch.append(job)
            else:
                best[job.node_id] = job

        # Emit metrics for batch-level supersede
        for s_job in superseded_in_batch:
            self.superseded_dropped_total += 1
            self._emit_metric("superseded_dropped_total")
            winner = best.get(s_job.node_id)
            if winner:
                self._emit_supersede_log(
                    "eval_superseded_on_enqueue",
                    winner,
                    superseded_job=s_job,
                )

        # Order by topo_order, then append nodes not in topo_order at end
        topo_index = {nid: i for i, nid in enumerate(topo_order)}
        ordered_ids = sorted(
            best.keys(),
            key=lambda nid: topo_index.get(nid, len(topo_order)),
        )

        enqueued: list[EvalJob] = []
        for nid in ordered_ids:
            job = best[nid]
            if self.enqueue(job):
                enqueued.append(job)

        return enqueued


class TriggerCoalescer:
    """Coalesces rapid change events within a time window.

    Merges rapid change events from fs-watch, mod-track, su-observer,
    and manual updates into one pending node set. Exactly one topological
    cascade is scheduled per coalesced batch. Events arriving during an
    active cascade are queued for the next batch.

    Bounded-wait flush: during continuous event streams, the window is
    capped at ``max_coalesce_ms`` from the first event in the batch to
    prevent starvation. Once the max wait is exceeded, the next trigger
    fires immediately instead of resetting the timer.

    Args:
        coalesce_ms: Coalescing window in milliseconds.
        callback: Function called with the set of affected node_ids.
        max_coalesce_ms: Maximum wait before forced flush (default: 3x window).
    """

    def __init__(
        self,
        coalesce_ms: float = VCAD_TRIGGER_COALESCE_MS,
        callback: Callable[[set[str]], None] | None = None,
        max_coalesce_ms: float | None = None,
    ):
        self.coalesce_ms = coalesce_ms
        self.max_coalesce_ms = (
            max_coalesce_ms if max_coalesce_ms is not None else coalesce_ms * 3
        )
        self.callback = callback
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._cascade_active: bool = False
        self._deferred: set[str] = set()
        self._window_start: float | None = None
        self.cascade_count: int = 0
        self.merged_events_total: int = 0
        # Publish effective window gauge
        self._publish_window_gauge()

    def _publish_window_gauge(self) -> None:
        """Set the coalesce_window_ms_effective gauge in centralized metrics."""
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            get_vcad_metrics().set_gauge(
                "coalesce_window_ms_effective", self.coalesce_ms
            )
        except Exception:
            pass

    @staticmethod
    def _emit_coalesce_metric(name: str) -> None:
        """Emit a metric increment to the centralized registry."""
        try:
            from supex_driver.connection.vcad_metrics import get_vcad_metrics

            get_vcad_metrics().increment(name)
        except Exception:
            pass

    def trigger(self, node_id: str, source: str = "") -> None:
        """Register a change event for a node.

        Events within the coalescing window are merged. Events during
        an active cascade are deferred to the next batch. If the bounded
        wait has been exceeded, the pending batch fires immediately.

        Args:
            node_id: The affected node identifier.
            source: Event source (fs-watch, mod-track, su-observer, manual).
        """
        with self._lock:
            self.merged_events_total += 1
            self._emit_coalesce_metric("coalesce_merged_events_total")
            if self._cascade_active:
                self._deferred.add(node_id)
                return
            self._pending.add(node_id)

            now = time.monotonic()
            if self._window_start is None:
                self._window_start = now

            # Cancel existing timer — we will reschedule
            if self._timer is not None:
                self._timer.cancel()

            # Bounded wait: if accumulating too long, fire immediately
            elapsed_ms = (now - self._window_start) * 1000.0
            if elapsed_ms >= self.max_coalesce_ms:
                delay = 0.0
            else:
                delay = self.coalesce_ms / 1000.0

            self._timer = threading.Timer(delay, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        """Execute the coalesced cascade callback."""
        with self._lock:
            nodes = self._pending.copy()
            self._pending.clear()
            self._timer = None
            self._cascade_active = True
            self._window_start = None

        if self.callback and nodes:
            try:
                self.callback(nodes)
            except Exception as e:
                logger.error(f"Trigger cascade callback error: {e}")

        with self._lock:
            self._cascade_active = False
            self.cascade_count += 1
            self._emit_coalesce_metric("coalesce_batches_total")
            if self._deferred:
                self._pending.update(self._deferred)
                self._deferred.clear()
                if self._pending:
                    self._window_start = time.monotonic()
                    self._timer = threading.Timer(
                        self.coalesce_ms / 1000.0,
                        self._fire,
                    )
                    self._timer.daemon = True
                    self._timer.start()

    def cancel(self) -> None:
        """Cancel any pending timer and reset window."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._window_start = None


class VCADPersistentState:
    """Manages persistent VCAD runtime state on disk.

    State is stored at ``<workspace>/.supex/vcad-state.json``.
    Writes are atomic (temp file + rename) to avoid partial state on crash.
    """

    def __init__(self, state_path: str | None = None, workspace: str | None = None):
        if state_path:
            self.state_path = state_path
        elif os.environ.get(VCAD_STATE_PATH_ENV):
            self.state_path = os.environ[VCAD_STATE_PATH_ENV]
        else:
            ws = workspace or os.environ.get("SUPEX_WORKSPACE")
            if ws:
                self.state_path = os.path.join(ws, ".supex", "vcad-state.json")
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
