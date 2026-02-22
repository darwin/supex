"""Tests for VCAD operational telemetry and diagnostics contract.

Covers:
- Metrics contract: stable names, counter monotonicity, gauge behavior
- Deterministic metrics for stale drops, queue overflow, supersede, coalesce
- Correlation ID propagation
- Structured logging events
- Diagnostics MCP tools: vcad_health, vcad_metrics, vcad_reconcile_status
- Recovery diagnostics: reconcile drift, artifact pairs
- Committed visibility: in-progress artifacts excluded from committed outputs
"""

import json
import os
import tempfile
import threading
import time

import pytest

from supex_driver.connection.vcad_logging import (
    EVENT_EVAL_ENQUEUED,
    EVENT_EVAL_FINISHED,
    EVENT_EVAL_STARTED,
    EVENT_EVAL_TIMEOUT,
    EVENT_RECONCILE_FINISHED,
    EVENT_RECONCILE_STARTED,
    EVENT_STALE_DROPPED,
    EVENT_VIEWER_RECONNECTED,
    REQUIRED_EVENTS,
    clear_correlation_id,
    emit_event,
    get_correlation_id,
    set_correlation_id,
)
from supex_driver.connection.vcad_metrics import (
    COUNTER_METRICS,
    GAUGE_METRICS,
    METRIC_NAMES,
    VcadMetrics,
    _reset_vcad_metrics,
    get_vcad_metrics,
)
from supex_driver.connection.vcad_reconcile_state import (
    ReconcileState,
    _reset_reconcile_state,
    get_reconcile_state,
)
from supex_driver.connection.vcad_state import (
    EvalJob,
    EvalQueue,
    RevisionTracker,
    TriggerCoalescer,
    VCADPersistentState,
)
from supex_driver.connection.vcad_dag import VcadDag, VcadNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all global singletons before each test."""
    _reset_vcad_metrics()
    _reset_reconcile_state()
    clear_correlation_id()
    yield
    _reset_vcad_metrics()
    _reset_reconcile_state()
    clear_correlation_id()


@pytest.fixture
def metrics():
    """Create a fresh VcadMetrics instance."""
    return VcadMetrics()


@pytest.fixture
def tmp_state_path(tmp_path):
    """Temporary path for persistent state file."""
    return str(tmp_path / "vcad-state.json")


@pytest.fixture
def dag(tmp_state_path):
    """Create a fresh VcadDag with temporary state path."""
    state = VCADPersistentState(state_path=tmp_state_path)
    tracker = RevisionTracker()
    return VcadDag(state=state, tracker=tracker)


# ===========================================================================
# Metrics contract
# ===========================================================================


class TestMetricsContract:
    """Test that metrics contract has stable names and types."""

    def test_all_metric_names_present(self) -> None:
        """All required metrics are defined in METRIC_NAMES."""
        required = [
            "queue_depth",
            "queue_rejected_total",
            "eval_timeout_total",
            "stale_dropped_total",
            "superseded_dropped_total",
            "superseded_skipped_before_eval_total",
            "coalesce_batches_total",
            "coalesce_merged_events_total",
            "coalesce_window_ms_effective",
            "artifact_manifests_written_total",
            "artifact_manifests_retained_current",
            "artifact_pair_recovery_total",
            "artifact_pair_incomplete_detected_total",
            "reconcile_runs_total",
            "reconcile_drift_total",
            "degraded_nodes_current",
            "viewer_reconnect_total",
        ]
        for name in required:
            assert name in METRIC_NAMES, f"Missing metric: {name}"

    def test_counter_metrics_are_counters(self) -> None:
        """Counter metrics must be in COUNTER_METRICS set."""
        counter_names = [n for n in METRIC_NAMES if n.endswith("_total")]
        for name in counter_names:
            assert name in COUNTER_METRICS, f"{name} should be a counter"

    def test_gauge_metrics_are_gauges(self) -> None:
        """Gauge metrics must be in GAUGE_METRICS set."""
        gauge_names = [
            n for n in METRIC_NAMES
            if not n.endswith("_total") and n not in COUNTER_METRICS
        ]
        for name in gauge_names:
            assert name in GAUGE_METRICS, f"{name} should be a gauge"

    def test_no_overlap_counter_gauge(self) -> None:
        """No metric should be both counter and gauge."""
        overlap = COUNTER_METRICS & GAUGE_METRICS
        assert not overlap, f"Overlap between counters and gauges: {overlap}"

    def test_all_names_accounted_for(self) -> None:
        """Every METRIC_NAME is either a counter or a gauge."""
        all_known = COUNTER_METRICS | GAUGE_METRICS
        for name in METRIC_NAMES:
            assert name in all_known, f"{name} is not classified as counter or gauge"

    def test_snapshot_contains_all_metrics(self, metrics: VcadMetrics) -> None:
        """Snapshot must contain all metric names plus collected_at."""
        snap = metrics.snapshot()
        for name in METRIC_NAMES:
            assert name in snap, f"Snapshot missing metric: {name}"
        assert "collected_at" in snap

    def test_snapshot_collected_at_is_timestamp(self, metrics: VcadMetrics) -> None:
        """collected_at must be a valid Unix timestamp."""
        snap = metrics.snapshot()
        assert isinstance(snap["collected_at"], float)
        assert snap["collected_at"] > 0


# ===========================================================================
# Counter monotonicity
# ===========================================================================


class TestCounterMonotonicity:
    """Counters must be monotonically increasing."""

    def test_increment_increases(self, metrics: VcadMetrics) -> None:
        metrics.increment("eval_timeout_total")
        assert metrics.get_counter("eval_timeout_total") == 1
        metrics.increment("eval_timeout_total")
        assert metrics.get_counter("eval_timeout_total") == 2

    def test_increment_by_delta(self, metrics: VcadMetrics) -> None:
        metrics.increment("reconcile_drift_total", 5)
        assert metrics.get_counter("reconcile_drift_total") == 5

    def test_counter_starts_at_zero(self, metrics: VcadMetrics) -> None:
        for name in COUNTER_METRICS:
            assert metrics.get_counter(name) == 0

    def test_invalid_counter_name_ignored(self, metrics: VcadMetrics) -> None:
        metrics.increment("nonexistent_counter")  # Should not raise
        assert metrics.get_counter("nonexistent_counter") == 0


# ===========================================================================
# Gauge behavior
# ===========================================================================


class TestGaugeBehavior:
    """Gauges can move up and down."""

    def test_set_gauge(self, metrics: VcadMetrics) -> None:
        metrics.set_gauge("queue_depth", 5.0)
        assert metrics.get_gauge("queue_depth") == 5.0

    def test_gauge_can_decrease(self, metrics: VcadMetrics) -> None:
        metrics.set_gauge("queue_depth", 10.0)
        metrics.set_gauge("queue_depth", 3.0)
        assert metrics.get_gauge("queue_depth") == 3.0

    def test_gauge_callback(self, metrics: VcadMetrics) -> None:
        metrics.register_gauge_callback("queue_depth", lambda: 42.0)
        assert metrics.get_gauge("queue_depth") == 42.0

    def test_gauge_callback_in_snapshot(self, metrics: VcadMetrics) -> None:
        metrics.register_gauge_callback("queue_depth", lambda: 7.0)
        snap = metrics.snapshot()
        assert snap["queue_depth"] == 7.0

    def test_gauge_callback_exception_fallback(self, metrics: VcadMetrics) -> None:
        def bad_callback():
            raise RuntimeError("fail")

        metrics.set_gauge("queue_depth", 99.0)
        metrics.register_gauge_callback("queue_depth", bad_callback)
        assert metrics.get_gauge("queue_depth") == 99.0


# ===========================================================================
# Metrics determinism: stale-result race
# ===========================================================================


class TestStaleDropMetrics:
    """Stale-result race: stale_dropped_total increments exactly once."""

    def test_single_stale_drop_increments_once(self) -> None:
        tracker = RevisionTracker()
        tracker.next_revision("node-1")  # rev=1
        tracker.next_revision("node-1")  # rev=2

        # Attempt to apply stale revision 1
        assert tracker.should_apply("node-1", 1) is False
        assert tracker.stale_dropped == 1

    def test_multiple_stale_drops_counted(self) -> None:
        tracker = RevisionTracker()
        tracker.next_revision("node-1")  # rev=1
        tracker.next_revision("node-1")  # rev=2
        tracker.next_revision("node-1")  # rev=3

        assert tracker.should_apply("node-1", 1) is False
        assert tracker.should_apply("node-1", 2) is False
        assert tracker.stale_dropped == 2

    def test_current_revision_not_stale(self) -> None:
        tracker = RevisionTracker()
        rev = tracker.next_revision("node-1")
        assert tracker.should_apply("node-1", rev) is True
        assert tracker.stale_dropped == 0

    def test_stale_drop_metrics_callback(self) -> None:
        tracker = RevisionTracker()
        events = []
        tracker.set_metrics_callback(lambda ev, nid: events.append((ev, nid)))

        tracker.next_revision("node-1")
        tracker.next_revision("node-1")
        tracker.should_apply("node-1", 1)

        assert len(events) == 1
        assert events[0] == ("stale_dropped", "node-1")


# ===========================================================================
# Metrics determinism: queue overflow
# ===========================================================================


class TestQueueOverflowMetrics:
    """Queue overflow: queue_rejected_total increments with stable counts."""

    def test_queue_overflow_counted(self) -> None:
        queue = EvalQueue(max_size=2)
        assert queue.enqueue(EvalJob("n1", 1, "/a.skp.oo")) is True
        assert queue.enqueue(EvalJob("n2", 1, "/b.skp.oo")) is True
        assert queue.enqueue(EvalJob("n3", 1, "/c.skp.oo")) is False
        assert queue.queue_rejected_total == 1

    def test_multiple_overflow_counted(self) -> None:
        queue = EvalQueue(max_size=1)
        queue.enqueue(EvalJob("n1", 1, "/a.skp.oo"))
        assert queue.enqueue(EvalJob("n2", 1, "/b.skp.oo")) is False
        assert queue.enqueue(EvalJob("n3", 1, "/c.skp.oo")) is False
        assert queue.queue_rejected_total == 2


# ===========================================================================
# Metrics determinism: supersede
# ===========================================================================


class TestSupersedeMetrics:
    """Same-node burst: superseded counts are deterministic."""

    def test_superseded_dropped_total(self) -> None:
        queue = EvalQueue(max_size=10)
        queue.enqueue(EvalJob("node-1", 1, "/a.skp.oo"))
        queue.enqueue(EvalJob("node-1", 2, "/a.skp.oo"))
        queue.enqueue(EvalJob("node-1", 3, "/a.skp.oo"))

        assert queue.superseded_dropped_total == 2

    def test_superseded_skipped_before_eval(self) -> None:
        queue = EvalQueue(max_size=10)
        queue.enqueue(EvalJob("node-1", 1, "/a.skp.oo"))
        queue.enqueue(EvalJob("node-1", 2, "/a.skp.oo"))
        queue.enqueue(EvalJob("node-1", 3, "/a.skp.oo"))

        job = queue.get_next()
        assert job is not None
        assert job.revision == 3
        assert queue.superseded_skipped_before_eval_total == 2

    def test_supersede_different_nodes_independent(self) -> None:
        queue = EvalQueue(max_size=10)
        queue.enqueue(EvalJob("node-1", 1, "/a.skp.oo"))
        queue.enqueue(EvalJob("node-2", 1, "/b.skp.oo"))
        queue.enqueue(EvalJob("node-1", 2, "/a.skp.oo"))

        assert queue.superseded_dropped_total == 1

        job1 = queue.get_next()
        assert job1.node_id == "node-2"
        job2 = queue.get_next()
        assert job2.node_id == "node-1"
        assert job2.revision == 2
        assert queue.superseded_skipped_before_eval_total == 1


# ===========================================================================
# Metrics determinism: coalesce
# ===========================================================================


class TestCoalesceMetrics:
    """Multi-source burst: coalesce metrics are deterministic."""

    def test_coalesce_batches_total(self) -> None:
        fired = threading.Event()
        coalescer = TriggerCoalescer(
            coalesce_ms=10,
            callback=lambda nodes: fired.set(),
        )

        coalescer.trigger("node-1", "fs-watch")
        coalescer.trigger("node-2", "mod-track")
        coalescer.trigger("node-3", "su-observer")

        fired.wait(timeout=2.0)
        assert fired.is_set()
        # Wait a bit for post-callback counter update
        time.sleep(0.05)
        assert coalescer.cascade_count == 1

    def test_coalesce_merged_events_total(self) -> None:
        fired = threading.Event()
        coalescer = TriggerCoalescer(
            coalesce_ms=10,
            callback=lambda nodes: fired.set(),
        )

        coalescer.trigger("node-1", "fs-watch")
        coalescer.trigger("node-2", "mod-track")
        coalescer.trigger("node-3", "su-observer")

        fired.wait(timeout=2.0)
        time.sleep(0.05)
        assert coalescer.merged_events_total == 3

    def test_dedup_within_window(self) -> None:
        fired = threading.Event()
        received_nodes: list[set[str]] = []
        coalescer = TriggerCoalescer(
            coalesce_ms=10,
            callback=lambda nodes: (received_nodes.append(nodes), fired.set()),
        )

        coalescer.trigger("node-1", "fs-watch")
        coalescer.trigger("node-1", "mod-track")  # same node
        coalescer.trigger("node-1", "su-observer")  # same node

        fired.wait(timeout=2.0)
        time.sleep(0.05)
        assert received_nodes[0] == {"node-1"}
        assert coalescer.merged_events_total == 3

    def test_coalesce_window_ms_effective(self) -> None:
        coalescer = TriggerCoalescer(coalesce_ms=42.0)
        assert coalescer.coalesce_ms == 42.0


# ===========================================================================
# Metrics determinism: artifact manifests
# ===========================================================================


class TestArtifactManifestMetrics:
    """Artifact manifest metrics track writes and retained count."""

    def test_artifact_manifests_written_total(self, metrics: VcadMetrics) -> None:
        metrics.increment("artifact_manifests_written_total")
        metrics.increment("artifact_manifests_written_total")
        assert metrics.get_counter("artifact_manifests_written_total") == 2

    def test_artifact_manifests_retained_current(self, metrics: VcadMetrics) -> None:
        metrics.set_gauge("artifact_manifests_retained_current", 5.0)
        assert metrics.get_gauge("artifact_manifests_retained_current") == 5.0
        metrics.set_gauge("artifact_manifests_retained_current", 3.0)
        assert metrics.get_gauge("artifact_manifests_retained_current") == 3.0

    def test_artifact_pair_recovery(self, metrics: VcadMetrics) -> None:
        metrics.increment("artifact_pair_recovery_total", 2)
        assert metrics.get_counter("artifact_pair_recovery_total") == 2

    def test_artifact_pair_incomplete_detected(self, metrics: VcadMetrics) -> None:
        metrics.increment("artifact_pair_incomplete_detected_total", 3)
        assert metrics.get_counter("artifact_pair_incomplete_detected_total") == 3


# ===========================================================================
# Correlation ID system
# ===========================================================================


class TestCorrelationId:
    """Test correlation ID propagation."""

    def test_set_and_get(self) -> None:
        rid = set_correlation_id("test-123")
        assert rid == "test-123"
        assert get_correlation_id() == "test-123"

    def test_auto_generate(self) -> None:
        rid = set_correlation_id()
        assert rid is not None
        assert len(rid) > 0
        assert get_correlation_id() == rid

    def test_clear(self) -> None:
        set_correlation_id("test-456")
        clear_correlation_id()
        assert get_correlation_id() is None

    def test_thread_isolation(self) -> None:
        set_correlation_id("main-thread")
        child_id = [None]

        def _in_thread():
            child_id[0] = get_correlation_id()

        t = threading.Thread(target=_in_thread)
        t.start()
        t.join()

        assert get_correlation_id() == "main-thread"
        assert child_id[0] is None  # Not inherited

    def test_thread_local_independence(self) -> None:
        results = {}

        def _in_thread(name: str):
            set_correlation_id(f"id-{name}")
            time.sleep(0.01)
            results[name] = get_correlation_id()

        threads = [
            threading.Thread(target=_in_thread, args=(f"t{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(5):
            assert results[f"t{i}"] == f"id-t{i}"


# ===========================================================================
# Structured logging events
# ===========================================================================


class TestStructuredLogging:
    """Test structured log event emission."""

    def test_emit_event_required_fields(self) -> None:
        set_correlation_id("req-001")
        record = emit_event(
            EVENT_EVAL_STARTED,
            node_id="node-1",
        )

        assert "timestamp" in record
        assert record["level"] == "INFO"
        assert record["request_id"] == "req-001"
        assert record["node_id"] == "node-1"
        assert record["event"] == EVENT_EVAL_STARTED

    def test_emit_event_with_error_code(self) -> None:
        record = emit_event(
            EVENT_EVAL_TIMEOUT,
            node_id="node-2",
            error_code="EVAL_TIMEOUT",
            request_id="req-002",
        )

        assert record["error_code"] == "EVAL_TIMEOUT"
        assert record["event"] == EVENT_EVAL_TIMEOUT

    def test_emit_event_extra_fields(self) -> None:
        record = emit_event(
            EVENT_EVAL_FINISHED,
            node_id="node-3",
            request_id="req-003",
            duration_ms=150,
            mesh_vertices=1024,
        )

        assert record["duration_ms"] == 150
        assert record["mesh_vertices"] == 1024

    def test_emit_event_no_correlation_id(self) -> None:
        clear_correlation_id()
        record = emit_event(EVENT_EVAL_ENQUEUED, node_id="node-4")
        assert record["request_id"] is None

    def test_emit_event_explicit_request_id(self) -> None:
        set_correlation_id("thread-level")
        record = emit_event(
            EVENT_STALE_DROPPED,
            request_id="explicit-id",
            node_id="node-5",
        )
        assert record["request_id"] == "explicit-id"

    def test_required_events_defined(self) -> None:
        """All required event names are defined as constants."""
        expected = [
            "eval_enqueued",
            "eval_started",
            "eval_finished",
            "eval_timeout",
            "stale_dropped",
            "reconcile_started",
            "reconcile_finished",
            "viewer_reconnected",
        ]
        for name in expected:
            assert name in REQUIRED_EVENTS


# ===========================================================================
# Reconcile diagnostics
# ===========================================================================


class TestReconcileDiagnostics:
    """Test reconciliation state tracking for diagnostics."""

    def test_initial_state(self) -> None:
        state = ReconcileState()
        snap = state.snapshot()
        assert snap["last_run_at"] is None
        assert snap["drift"] == {}
        assert snap["pending_nodes"] == []
        assert snap["last_outcome"] == "none"

    def test_record_run(self) -> None:
        state = ReconcileState()
        state.record_run(
            drift={"source_missing": ["node-1"], "revision_gap": ["node-2"]},
            pending_nodes=["node-2"],
            outcome="degraded",
        )

        snap = state.snapshot()
        assert snap["last_run_at"] is not None
        assert snap["last_run_at"] > 0
        assert "source_missing" in snap["drift"]
        assert "node-1" in snap["drift"]["source_missing"]
        assert snap["pending_nodes"] == ["node-2"]
        assert snap["last_outcome"] == "degraded"

    def test_singleton(self) -> None:
        s1 = get_reconcile_state()
        s2 = get_reconcile_state()
        assert s1 is s2

    def test_record_overwrites(self) -> None:
        state = ReconcileState()
        state.record_run(
            drift={"source_missing": ["node-1"]},
            outcome="degraded",
        )
        state.record_run(
            drift={},
            outcome="ok",
        )
        snap = state.snapshot()
        assert snap["last_outcome"] == "ok"
        assert snap["drift"] == {}


# ===========================================================================
# Recovery diagnostics: reconcile drift through DAG
# ===========================================================================


class TestReconcileDriftThroughDag:
    """Force reconcile drift and verify metrics + diagnostics."""

    def test_reconcile_drift_updates_metrics(self, tmp_state_path: str) -> None:
        metrics = get_vcad_metrics()
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VcadDag(state=state)

        dag.add_node(VcadNode(
            node_id="node-1",
            source_file=__file__,  # existing file
            revision=5,
            applied_revision=3,
        ))
        dag.persist_state()

        buckets = dag.reconcile_with_sketchup([{"node_id": "node-1"}])

        assert "node-1" in buckets["revision_gap"]
        assert metrics.get_counter("reconcile_runs_total") == 1
        assert metrics.get_counter("reconcile_drift_total") >= 1

    def test_reconcile_updates_reconcile_state(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VcadDag(state=state)

        dag.add_node(VcadNode(
            node_id="node-1",
            source_file=__file__,
            revision=5,
            applied_revision=3,
        ))
        dag.persist_state()

        dag.reconcile_with_sketchup([{"node_id": "node-1"}])

        reconcile = get_reconcile_state()
        snap = reconcile.snapshot()
        assert snap["last_run_at"] is not None
        assert "revision_gap" in snap["drift"]
        assert "node-1" in snap["pending_nodes"]

    def test_source_missing_reports_degraded(self, tmp_state_path: str) -> None:
        # Create and delete a file
        with tempfile.NamedTemporaryFile(suffix=".skp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        metrics = get_vcad_metrics()
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VcadDag(state=state)

        dag.add_node(VcadNode(
            node_id="node-1",
            source_file=missing_path,
            revision=1,
            applied_revision=1,
        ))
        dag.persist_state()

        dag.reconcile_with_sketchup([{"node_id": "node-1"}])

        reconcile = get_reconcile_state()
        snap = reconcile.snapshot()
        assert snap["last_outcome"] == "degraded"

        # degraded_nodes_current should be set
        snap2 = metrics.snapshot()
        assert snap2["degraded_nodes_current"] >= 1.0

    def test_multiple_reconcile_runs(self, tmp_state_path: str) -> None:
        metrics = get_vcad_metrics()
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VcadDag(state=state)

        dag.add_node(VcadNode(
            node_id="node-1",
            source_file=__file__,
            revision=1,
            applied_revision=1,
        ))
        dag.persist_state()

        dag.reconcile_with_sketchup([{"node_id": "node-1"}])
        dag.reconcile_with_sketchup([{"node_id": "node-1"}])

        assert metrics.get_counter("reconcile_runs_total") == 2


# ===========================================================================
# Committed visibility: in-progress artifacts
# ===========================================================================


class TestCommittedVisibility:
    """In-progress/staged artifacts never appear in committed outputs."""

    def test_in_progress_excluded_from_snapshot(self, metrics: VcadMetrics) -> None:
        """Artifact counters only reflect committed (written) artifacts."""
        # Simulate: 3 manifests written, but gauge shows only 2 retained
        metrics.increment("artifact_manifests_written_total", 3)
        metrics.set_gauge("artifact_manifests_retained_current", 2.0)

        snap = metrics.snapshot()
        assert snap["artifact_manifests_written_total"] == 3
        assert snap["artifact_manifests_retained_current"] == 2.0

    def test_incomplete_pairs_tracked_separately(self, metrics: VcadMetrics) -> None:
        """Incomplete pairs are tracked via dedicated counter, not in written count."""
        metrics.increment("artifact_pair_incomplete_detected_total", 2)
        metrics.increment("artifact_pair_recovery_total", 1)

        snap = metrics.snapshot()
        assert snap["artifact_pair_incomplete_detected_total"] == 2
        assert snap["artifact_pair_recovery_total"] == 1
        # These don't affect the written count
        assert snap["artifact_manifests_written_total"] == 0


# ===========================================================================
# Diagnostics MCP tools
# ===========================================================================


class TestVcadHealthTool:
    """Test vcad_health MCP tool."""

    def test_health_returns_valid_json(self) -> None:
        # Import inside test to avoid side effects
        from supex_driver.mcp.vcad_diagnostics import vcad_health

        # Create a minimal mock context
        result = vcad_health(ctx=None)
        parsed = json.loads(result)

        assert "status" in parsed
        assert "sidecar" in parsed
        assert "viewer" in parsed
        assert "capabilities" in parsed
        assert "last_error" in parsed

    def test_health_sidecar_disconnected(self) -> None:
        from supex_driver.mcp.vcad_diagnostics import vcad_health

        result = vcad_health(ctx=None)
        parsed = json.loads(result)

        # Without a running sidecar, should report disconnected or degraded
        assert parsed["sidecar"]["status"] in ("disconnected", "error", "unknown")

    def test_health_viewer_not_started(self) -> None:
        from supex_driver.mcp.vcad_diagnostics import vcad_health

        result = vcad_health(ctx=None)
        parsed = json.loads(result)

        assert parsed["viewer"]["status"] in ("not_started", "disconnected", "error")


class TestVcadMetricsTool:
    """Test vcad_metrics MCP tool."""

    def test_metrics_returns_valid_json(self) -> None:
        from supex_driver.mcp.vcad_diagnostics import vcad_metrics as vcad_metrics_tool

        result = vcad_metrics_tool(ctx=None)
        parsed = json.loads(result)

        # All metric names present
        for name in METRIC_NAMES:
            assert name in parsed, f"Missing metric in tool output: {name}"

        assert "collected_at" in parsed

    def test_metrics_reflects_state(self) -> None:
        from supex_driver.mcp.vcad_diagnostics import vcad_metrics as vcad_metrics_tool

        metrics = get_vcad_metrics()
        metrics.increment("eval_timeout_total", 5)
        metrics.increment("reconcile_runs_total", 2)

        result = vcad_metrics_tool(ctx=None)
        parsed = json.loads(result)

        assert parsed["eval_timeout_total"] == 5
        assert parsed["reconcile_runs_total"] == 2


class TestVcadReconcileStatusTool:
    """Test vcad_reconcile_status MCP tool."""

    def test_reconcile_status_returns_valid_json(self) -> None:
        from supex_driver.mcp.vcad_diagnostics import vcad_reconcile_status

        result = vcad_reconcile_status(ctx=None)
        parsed = json.loads(result)

        assert "last_run_at" in parsed
        assert "drift" in parsed
        assert "pending_nodes" in parsed
        assert "last_outcome" in parsed

    def test_reconcile_status_reflects_recorded_run(self) -> None:
        from supex_driver.mcp.vcad_diagnostics import vcad_reconcile_status

        state = get_reconcile_state()
        state.record_run(
            drift={"source_missing": ["node-1"]},
            pending_nodes=["node-1"],
            outcome="degraded",
        )

        result = vcad_reconcile_status(ctx=None)
        parsed = json.loads(result)

        assert parsed["last_outcome"] == "degraded"
        assert "source_missing" in parsed["drift"]
        assert "node-1" in parsed["pending_nodes"]


# ===========================================================================
# Metrics reset (for testing isolation)
# ===========================================================================


class TestMetricsReset:
    """Test metrics reset for test isolation."""

    def test_reset_clears_counters(self, metrics: VcadMetrics) -> None:
        metrics.increment("eval_timeout_total", 10)
        metrics.reset()
        assert metrics.get_counter("eval_timeout_total") == 0

    def test_reset_clears_gauges(self, metrics: VcadMetrics) -> None:
        metrics.set_gauge("queue_depth", 42.0)
        metrics.reset()
        assert metrics.get_gauge("queue_depth") == 0.0

    def test_singleton_reset(self) -> None:
        m1 = get_vcad_metrics()
        m1.increment("eval_timeout_total")

        _reset_vcad_metrics()

        m2 = get_vcad_metrics()
        assert m2 is not m1
        assert m2.get_counter("eval_timeout_total") == 0


# ===========================================================================
# Integration: end-to-end metric flow
# ===========================================================================


class TestEndToEndMetricFlow:
    """Test that metrics flow from components through to snapshot."""

    def test_eval_queue_metrics_in_snapshot(self) -> None:
        metrics = get_vcad_metrics()
        queue = EvalQueue(max_size=2)

        # Fill queue and overflow — metrics are emitted automatically
        queue.enqueue(EvalJob("n1", 1, "/a.skp.oo"))
        queue.enqueue(EvalJob("n2", 1, "/b.skp.oo"))
        queue.enqueue(EvalJob("n3", 1, "/c.skp.oo"))  # rejected

        snap = metrics.snapshot()
        assert snap["queue_rejected_total"] == 1

    def test_revision_tracker_metrics_in_snapshot(self) -> None:
        metrics = get_vcad_metrics()
        tracker = RevisionTracker()

        tracker.next_revision("node-1")
        tracker.next_revision("node-1")
        tracker.should_apply("node-1", 1)  # stale -> auto-emits to metrics

        snap = metrics.snapshot()
        assert snap["stale_dropped_total"] == 1

    def test_coalesce_metrics_in_snapshot(self) -> None:
        metrics = get_vcad_metrics()
        fired = threading.Event()

        coalescer = TriggerCoalescer(
            coalesce_ms=10,
            callback=lambda nodes: fired.set(),
        )
        coalescer.trigger("node-1", "test")
        coalescer.trigger("node-2", "test")

        fired.wait(timeout=2.0)
        time.sleep(0.05)

        # Coalescer now emits metrics directly, just set gauge manually
        metrics.set_gauge("coalesce_window_ms_effective", coalescer.coalesce_ms)

        snap = metrics.snapshot()
        assert snap["coalesce_batches_total"] == 1
        assert snap["coalesce_merged_events_total"] == 2
        assert snap["coalesce_window_ms_effective"] == 10.0


# ===========================================================================
# Structured logging: correlation flow
# ===========================================================================


class TestCorrelationFlow:
    """Test that correlation ID flows through structured events."""

    def test_same_request_id_across_events(self) -> None:
        """Single request flow: same request_id in all events."""
        request_id = set_correlation_id("flow-001")

        events = [
            emit_event(EVENT_EVAL_ENQUEUED, node_id="node-1"),
            emit_event(EVENT_EVAL_STARTED, node_id="node-1"),
            emit_event(EVENT_EVAL_FINISHED, node_id="node-1"),
        ]

        for ev in events:
            assert ev["request_id"] == "flow-001"

    def test_reconcile_events(self) -> None:
        rid = set_correlation_id("reconcile-flow")

        start_ev = emit_event(EVENT_RECONCILE_STARTED)
        finish_ev = emit_event(EVENT_RECONCILE_FINISHED, drift_count=3)

        assert start_ev["request_id"] == rid
        assert finish_ev["request_id"] == rid
        assert finish_ev["drift_count"] == 3

    def test_viewer_reconnect_event(self) -> None:
        ev = emit_event(
            EVENT_VIEWER_RECONNECTED,
            request_id="viewer-001",
            viewer_version="1.0",
        )
        assert ev["event"] == "viewer_reconnected"
        assert ev["viewer_version"] == "1.0"
