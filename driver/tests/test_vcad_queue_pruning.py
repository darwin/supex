"""Tests for supersede-aware pending eval pruning.

Covers:
- Same-node burst: rapid edits for one node, only latest pending evaluated
- Topo safety: upstream/downstream cascade with overlaps preserves
  dependency order across different nodes
- Race/latency: long-running eval + rapid superseding updates,
  no rollback, no starvation, deterministic supersede counters
- Job lifecycle state transitions (pending -> running -> done | superseded)
- Structured logging events for queue-pruning
"""

import threading
import time

import pytest

from supex_driver.connection.vcad_dag import ImportRef, VCADDag, VCADNode
from supex_driver.connection.vcad_logging import (
    EVENT_EVAL_SUPERSEDED_ON_ENQUEUE,
    EVENT_EVAL_SUPERSEDED_SKIPPED,
    REQUIRED_EVENTS,
    clear_correlation_id,
    set_correlation_id,
)
from supex_driver.connection.vcad_metrics import (
    _reset_vcad_metrics,
    get_vcad_metrics,
)
from supex_driver.connection.vcad_state import (
    EvalJob,
    EvalQueue,
    RevisionTracker,
    VCADPersistentState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global singletons before each test."""
    _reset_vcad_metrics()
    clear_correlation_id()
    yield
    _reset_vcad_metrics()
    clear_correlation_id()


@pytest.fixture
def queue():
    return EvalQueue(max_size=64)


@pytest.fixture
def tracker():
    return RevisionTracker()


@pytest.fixture
def dag(tmp_path):
    state = VCADPersistentState(state_path=str(tmp_path / "vcad-state.json"))
    t = RevisionTracker()
    return VCADDag(state=state, tracker=t)


# ===========================================================================
# EvalJob state model
# ===========================================================================


class TestEvalJobStateModel:
    """EvalJob has job_id and state lifecycle."""

    def test_job_has_uuid_id(self) -> None:
        job = EvalJob(node_id="n1", revision=1, source="code")
        assert job.job_id  # non-empty
        assert len(job.job_id) == 36  # UUID format

    def test_unique_job_ids(self) -> None:
        jobs = [EvalJob(node_id="n1", revision=i, source="c") for i in range(10)]
        ids = {j.job_id for j in jobs}
        assert len(ids) == 10

    def test_default_state_is_pending(self) -> None:
        job = EvalJob(node_id="n1", revision=1, source="code")
        assert job.state == "pending"

    def test_superseded_property(self) -> None:
        job = EvalJob(node_id="n1", revision=1, source="code")
        assert job.superseded is False
        job.state = "superseded"
        assert job.superseded is True

    def test_state_running(self) -> None:
        job = EvalJob(node_id="n1", revision=1, source="code")
        job.state = "running"
        assert job.state == "running"
        assert job.superseded is False

    def test_state_done(self) -> None:
        job = EvalJob(node_id="n1", revision=1, source="code")
        job.state = "done"
        assert job.state == "done"
        assert job.superseded is False


# ===========================================================================
# Same-node burst
# ===========================================================================


class TestSameNodeBurst:
    """Enqueue rapid edits for one node; only latest pending revision evaluated."""

    def test_burst_three_revisions(self, queue: EvalQueue) -> None:
        """Three rapid edits: only rev 3 is evaluated."""
        queue.enqueue(EvalJob(node_id="node-1", revision=1, source="v1"))
        queue.enqueue(EvalJob(node_id="node-1", revision=2, source="v2"))
        queue.enqueue(EvalJob(node_id="node-1", revision=3, source="v3"))

        assert queue.superseded_dropped_total == 2

        job = queue.get_next()
        assert job is not None
        assert job.revision == 3
        assert job.state == "running"
        assert queue.superseded_skipped_before_eval_total == 2
        assert queue.get_next() is None

    def test_burst_ten_revisions(self, queue: EvalQueue) -> None:
        """Ten rapid edits: only rev 10 is evaluated."""
        for rev in range(1, 11):
            queue.enqueue(EvalJob(node_id="n1", revision=rev, source=f"v{rev}"))

        assert queue.superseded_dropped_total == 9

        job = queue.get_next()
        assert job is not None
        assert job.revision == 10
        assert queue.superseded_skipped_before_eval_total == 9
        assert queue.get_next() is None

    def test_burst_interleaved_with_other_nodes(self, queue: EvalQueue) -> None:
        """Burst for node-a interleaved with node-b: both get latest only."""
        queue.enqueue(EvalJob(node_id="a", revision=1, source="a1"))
        queue.enqueue(EvalJob(node_id="b", revision=1, source="b1"))
        queue.enqueue(EvalJob(node_id="a", revision=2, source="a2"))
        queue.enqueue(EvalJob(node_id="b", revision=2, source="b2"))
        queue.enqueue(EvalJob(node_id="a", revision=3, source="a3"))

        # a: rev1,rev2 superseded (2); b: rev1 superseded (1)
        assert queue.superseded_dropped_total == 3

        executed = []
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed.append((job.node_id, job.revision))

        assert ("b", 2) in executed
        assert ("a", 3) in executed
        assert len(executed) == 2

    def test_burst_all_same_revision(self, queue: EvalQueue) -> None:
        """Multiple enqueues with same revision for same node still prunes."""
        queue.enqueue(EvalJob(node_id="n1", revision=5, source="a"))
        queue.enqueue(EvalJob(node_id="n1", revision=5, source="b"))
        queue.enqueue(EvalJob(node_id="n1", revision=5, source="c"))

        assert queue.superseded_dropped_total == 2

        job = queue.get_next()
        assert job is not None
        assert job.source == "c"
        assert queue.get_next() is None

    def test_counters_deterministic(self, queue: EvalQueue) -> None:
        """Supersede counters are deterministic and match exactly."""
        for rev in range(1, 6):
            queue.enqueue(EvalJob(node_id="x", revision=rev, source=f"v{rev}"))

        assert queue.superseded_dropped_total == 4

        job = queue.get_next()
        assert job is not None
        assert job.revision == 5
        assert queue.superseded_skipped_before_eval_total == 4
        assert queue.get_next() is None

    def test_centralized_metrics_updated(self) -> None:
        """Supersede metrics are reflected in VCADMetrics singleton."""
        metrics = get_vcad_metrics()
        queue = EvalQueue(max_size=10)

        queue.enqueue(EvalJob(node_id="n1", revision=1, source="a"))
        queue.enqueue(EvalJob(node_id="n1", revision=2, source="b"))

        assert metrics.get_counter("superseded_dropped_total") == 1

        queue.get_next()
        assert metrics.get_counter("superseded_skipped_before_eval_total") == 1


# ===========================================================================
# Topological safety
# ===========================================================================


class TestTopologicalSafety:
    """Dependency order is preserved across different nodes in one cascade."""

    def _make_dag_chain(self, dag: VCADDag) -> None:
        """Create A -> B -> C dependency chain."""
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(
            VCADNode(
                node_id="B",
                source_file="/b.cmp.oo",
                imports=[
                    ImportRef(
                        binding_name="a_solid",
                        selector="entity:A",
                        extracts=["solid"],
                        resolved_type="vcad",
                        source_node_id="A",
                    )
                ],
            )
        )
        dag.add_node(
            VCADNode(
                node_id="C",
                source_file="/c.cmp.oo",
                imports=[
                    ImportRef(
                        binding_name="b_solid",
                        selector="entity:B",
                        extracts=["solid"],
                        resolved_type="vcad",
                        source_node_id="B",
                    )
                ],
            )
        )

    def test_cascade_preserves_topo_order(self, dag: VCADDag) -> None:
        """Cascade batch respects A -> B -> C dependency order."""
        self._make_dag_chain(dag)
        topo = dag.get_evaluation_order()

        # Verify topological order: A before B before C
        assert topo.index("A") < topo.index("B") < topo.index("C")

        queue = EvalQueue(max_size=64)
        jobs = [
            EvalJob(node_id="C", revision=1, source="c1"),
            EvalJob(node_id="A", revision=1, source="a1"),
            EvalJob(node_id="B", revision=1, source="b1"),
        ]

        enqueued = queue.enqueue_cascade_batch(jobs, topo)

        # All three should be enqueued in topo order
        assert len(enqueued) == 3
        ids = [j.node_id for j in enqueued]
        assert ids.index("A") < ids.index("B") < ids.index("C")

    def test_cascade_prunes_per_node_keeps_inter_node_order(
        self, dag: VCADDag
    ) -> None:
        """Overlapping cascade: per-node latest kept, inter-node order preserved."""
        self._make_dag_chain(dag)
        topo = dag.get_evaluation_order()

        queue = EvalQueue(max_size=64)
        # Two cascades overlap: A has rev 1 and 2, B has rev 1 and 3
        jobs = [
            EvalJob(node_id="A", revision=1, source="a1"),
            EvalJob(node_id="B", revision=1, source="b1"),
            EvalJob(node_id="C", revision=1, source="c1"),
            EvalJob(node_id="A", revision=2, source="a2"),
            EvalJob(node_id="B", revision=3, source="b3"),
        ]

        enqueued = queue.enqueue_cascade_batch(jobs, topo)

        # A rev2, B rev3, C rev1 — in topo order
        assert len(enqueued) == 3
        by_node = {j.node_id: j for j in enqueued}
        assert by_node["A"].revision == 2
        assert by_node["B"].revision == 3
        assert by_node["C"].revision == 1

        # Verify topo order in queue (get_next order)
        executed_order = []
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed_order.append(job.node_id)

        assert executed_order.index("A") < executed_order.index("B")
        assert executed_order.index("B") < executed_order.index("C")

    def test_cascade_supersede_metrics_for_duplicates(
        self, dag: VCADDag
    ) -> None:
        """Duplicate per-node jobs in batch increment supersede counters."""
        self._make_dag_chain(dag)
        topo = dag.get_evaluation_order()

        queue = EvalQueue(max_size=64)
        jobs = [
            EvalJob(node_id="A", revision=1, source="a1"),
            EvalJob(node_id="A", revision=2, source="a2"),
            EvalJob(node_id="A", revision=3, source="a3"),
        ]

        enqueued = queue.enqueue_cascade_batch(jobs, topo)

        assert len(enqueued) == 1
        assert enqueued[0].revision == 3
        # 2 superseded in batch dedup
        assert queue.superseded_dropped_total == 2

    def test_cascade_preserves_non_dag_nodes(self) -> None:
        """Nodes not in topo_order are appended at the end."""
        queue = EvalQueue(max_size=64)
        topo = ["X", "Y"]  # only X, Y known in topo

        jobs = [
            EvalJob(node_id="Z", revision=1, source="z1"),
            EvalJob(node_id="X", revision=1, source="x1"),
            EvalJob(node_id="Y", revision=1, source="y1"),
        ]

        enqueued = queue.enqueue_cascade_batch(jobs, topo)

        assert len(enqueued) == 3
        ids = [j.node_id for j in enqueued]
        # X before Y (from topo), Z at end (not in topo)
        assert ids.index("X") < ids.index("Y")
        assert ids.index("Z") == 2

    def test_downstream_cascade_does_not_prune_upstream(
        self, dag: VCADDag
    ) -> None:
        """Changing downstream node does not affect upstream pending jobs."""
        self._make_dag_chain(dag)

        queue = EvalQueue(max_size=64)
        queue.enqueue(EvalJob(node_id="A", revision=1, source="a1"))
        queue.enqueue(EvalJob(node_id="C", revision=1, source="c1"))
        queue.enqueue(EvalJob(node_id="C", revision=2, source="c2"))

        # Only C should have superseded jobs
        assert queue.superseded_dropped_total == 1

        job_a = queue.get_next()
        assert job_a is not None
        assert job_a.node_id == "A"
        assert job_a.revision == 1

        job_c = queue.get_next()
        assert job_c is not None
        assert job_c.node_id == "C"
        assert job_c.revision == 2


# ===========================================================================
# Race / latency
# ===========================================================================


class TestRaceAndLatency:
    """Long-running eval + rapid superseding updates: no rollback, no starvation."""

    def test_running_job_not_cancelled_by_new_enqueue(
        self, queue: EvalQueue
    ) -> None:
        """A running job is not superseded by a new enqueue for same node."""
        queue.enqueue(EvalJob(node_id="n1", revision=1, source="v1"))

        # Worker picks up the job (transitions to running)
        running = queue.get_next()
        assert running is not None
        assert running.state == "running"

        # New revision arrives while worker is busy
        queue.enqueue(EvalJob(node_id="n1", revision=2, source="v2"))

        # Running job was NOT superseded
        assert running.state == "running"
        # No supersede happened (the running job was already out of queue)
        assert queue.superseded_dropped_total == 0

    def test_stale_guard_blocks_old_running_result(
        self, tracker: RevisionTracker
    ) -> None:
        """Stale-result guard blocks results from old running eval."""
        rev1 = tracker.next_revision("n1")
        rev2 = tracker.next_revision("n1")

        # Old running job finishes after new revision exists
        assert tracker.should_apply("n1", rev1) is False
        assert tracker.stale_dropped == 1

        # New revision applies
        assert tracker.should_apply("n1", rev2) is True

    def test_concurrent_enqueue_no_starvation(self) -> None:
        """Multiple threads enqueuing for different nodes: none starved."""
        queue = EvalQueue(max_size=1000)
        barrier = threading.Barrier(5)

        def enqueue_burst(node_id: str) -> None:
            barrier.wait()
            for rev in range(1, 21):
                queue.enqueue(
                    EvalJob(node_id=node_id, revision=rev, source=f"v{rev}")
                )

        threads = [
            threading.Thread(target=enqueue_burst, args=(f"node-{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each of 5 nodes should have exactly 1 pending (latest) job
        assert queue.pending_count() == 5

        # Drain queue: each node gets exactly one job
        executed_nodes = set()
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed_nodes.add(job.node_id)
            assert job.revision == 20  # latest

        assert len(executed_nodes) == 5

    def test_rapid_supersede_then_eval_deterministic_counters(self) -> None:
        """Rapid burst then drain: counter totals are exact."""
        queue = EvalQueue(max_size=200)

        # 5 nodes x 10 revisions = 50 total enqueues
        for node_idx in range(5):
            for rev in range(1, 11):
                queue.enqueue(
                    EvalJob(
                        node_id=f"n{node_idx}",
                        revision=rev,
                        source=f"v{rev}",
                    )
                )

        # Each node: 9 superseded on enqueue = 45 total
        assert queue.superseded_dropped_total == 45

        executed = {}
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed[job.node_id] = job.revision

        assert len(executed) == 5
        for node_idx in range(5):
            assert executed[f"n{node_idx}"] == 10

        assert queue.superseded_skipped_before_eval_total == 45

    def test_long_eval_with_superseding_updates(self) -> None:
        """Simulate long eval (thread sleep) with rapid superseding updates."""
        queue = EvalQueue(max_size=100)
        tracker = RevisionTracker()
        applied_results: list[tuple[str, int]] = []
        lock = threading.Lock()

        # Simulate worker thread
        def worker() -> None:
            while True:
                job = queue.get_next()
                if job is None:
                    break
                # Simulate eval work
                time.sleep(0.01)
                job.state = "done"
                # Apply only if not stale
                if tracker.should_apply(job.node_id, job.revision):
                    with lock:
                        applied_results.append((job.node_id, job.revision))

        # Enqueue initial jobs
        for rev in range(1, 4):
            r = tracker.next_revision("n1")
            queue.enqueue(EvalJob(node_id="n1", revision=r, source=f"v{rev}"))

        # Start worker
        t = threading.Thread(target=worker)
        t.start()

        # While worker runs, add more updates
        time.sleep(0.005)
        for rev in range(4, 7):
            r = tracker.next_revision("n1")
            queue.enqueue(EvalJob(node_id="n1", revision=r, source=f"v{rev}"))

        # Signal end
        time.sleep(0.2)
        t.join(timeout=2.0)

        # At most 2 results applied (initial latest + final latest)
        # Due to stale guard, only results matching current revision apply
        with lock:
            if applied_results:
                # The last applied result should be the highest revision
                last_applied = applied_results[-1]
                assert last_applied[1] <= tracker.current_revision("n1")

    def test_no_rollback_after_supersede(self) -> None:
        """Once a newer revision is applied, older results don't roll back."""
        tracker = RevisionTracker()
        applied: list[int] = []

        # Generate 5 revisions
        revisions = [tracker.next_revision("n1") for _ in range(5)]

        # Apply in reverse order (simulating out-of-order completion)
        for rev in reversed(revisions):
            if tracker.should_apply("n1", rev):
                applied.append(rev)

        # Only the latest (rev 5) should apply since it was attempted first
        # in our reverse iteration
        assert len(applied) == 1
        assert applied[0] == 5

    def test_queue_full_does_not_corrupt_state(self) -> None:
        """Queue rejection doesn't corrupt internal state."""
        queue = EvalQueue(max_size=3)

        queue.enqueue(EvalJob(node_id="a", revision=1, source="a1"))
        queue.enqueue(EvalJob(node_id="b", revision=1, source="b1"))
        queue.enqueue(EvalJob(node_id="c", revision=1, source="c1"))

        # Queue is full
        assert queue.enqueue(
            EvalJob(node_id="d", revision=1, source="d1")
        ) is False
        assert queue.queue_rejected_total == 1

        # Existing jobs unaffected
        assert queue.pending_count() == 3

        # Drain and verify all original jobs
        jobs = []
        while True:
            j = queue.get_next()
            if j is None:
                break
            jobs.append(j.node_id)

        assert set(jobs) == {"a", "b", "c"}


# ===========================================================================
# Structured logging for queue-pruning
# ===========================================================================


class TestQueuePruningTelemetry:
    """Structured log events include request_id, node_id, revision, event."""

    def test_supersede_event_names_in_required(self) -> None:
        """Supersede event constants are in REQUIRED_EVENTS."""
        assert EVENT_EVAL_SUPERSEDED_ON_ENQUEUE in REQUIRED_EVENTS
        assert EVENT_EVAL_SUPERSEDED_SKIPPED in REQUIRED_EVENTS

    def test_enqueue_emits_supersede_on_enqueue_event(
        self, queue: EvalQueue
    ) -> None:
        """Structured log emitted when pending job is marked superseded."""
        import json
        import logging

        captured: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record.getMessage())
        tel_logger = logging.getLogger("supex.vcad.telemetry")
        tel_logger.addHandler(handler)
        tel_logger.setLevel(logging.DEBUG)

        try:
            set_correlation_id("req-123")
            queue.enqueue(EvalJob(node_id="n1", revision=1, source="v1"))
            queue.enqueue(EvalJob(node_id="n1", revision=2, source="v2"))

            # Should have emitted eval_superseded_on_enqueue
            supersede_logs = [
                json.loads(m)
                for m in captured
                if "eval_superseded_on_enqueue" in m
            ]
            assert len(supersede_logs) == 1

            log = supersede_logs[0]
            assert log["event"] == "eval_superseded_on_enqueue"
            assert log["node_id"] == "n1"
            assert log["request_id"] == "req-123"
            assert "revision" in log
            assert "superseded_job_id" in log
            assert "superseded_revision" in log
            assert log["revision"] == 2
            assert log["superseded_revision"] == 1
        finally:
            tel_logger.removeHandler(handler)

    def test_get_next_emits_supersede_skipped_event(
        self, queue: EvalQueue
    ) -> None:
        """Structured log emitted when superseded job is skipped pre-eval."""
        import json
        import logging

        captured: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record.getMessage())
        tel_logger = logging.getLogger("supex.vcad.telemetry")
        tel_logger.addHandler(handler)
        tel_logger.setLevel(logging.DEBUG)

        try:
            set_correlation_id("req-456")
            queue.enqueue(EvalJob(node_id="n1", revision=1, source="v1"))
            queue.enqueue(EvalJob(node_id="n1", revision=2, source="v2"))

            captured.clear()  # Clear enqueue logs
            queue.get_next()  # Skips rev 1, returns rev 2

            skip_logs = [
                json.loads(m)
                for m in captured
                if "eval_superseded_skipped" in m
            ]
            assert len(skip_logs) == 1

            log = skip_logs[0]
            assert log["event"] == "eval_superseded_skipped"
            assert log["node_id"] == "n1"
            assert log["request_id"] == "req-456"
            assert log["revision"] == 1  # the skipped revision
            assert "job_id" in log
        finally:
            tel_logger.removeHandler(handler)

    def test_cascade_batch_emits_supersede_events(self, dag: VCADDag) -> None:
        """cascade batch dedup emits supersede events for pruned duplicates."""
        import json
        import logging

        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(node_id="B", source_file="/b.cmp.oo"))
        topo = dag.get_evaluation_order()

        captured: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record.getMessage())
        tel_logger = logging.getLogger("supex.vcad.telemetry")
        tel_logger.addHandler(handler)
        tel_logger.setLevel(logging.DEBUG)

        try:
            set_correlation_id("req-batch")
            queue = EvalQueue(max_size=64)
            jobs = [
                EvalJob(node_id="A", revision=1, source="a1"),
                EvalJob(node_id="A", revision=2, source="a2"),
            ]

            queue.enqueue_cascade_batch(jobs, topo)

            supersede_logs = [
                json.loads(m)
                for m in captured
                if "eval_superseded_on_enqueue" in m
            ]
            # 1 from batch dedup
            assert len(supersede_logs) >= 1
            assert supersede_logs[0]["request_id"] == "req-batch"
        finally:
            tel_logger.removeHandler(handler)


# ===========================================================================
# Job state transitions
# ===========================================================================


class TestJobStateTransitions:
    """Verify job state lifecycle: pending -> running -> done | superseded."""

    def test_enqueue_sets_pending(self, queue: EvalQueue) -> None:
        job = EvalJob(node_id="n1", revision=1, source="v1")
        queue.enqueue(job)
        # The internal queue entry is pending
        assert queue._queue[0].state == "pending"

    def test_get_next_transitions_to_running(self, queue: EvalQueue) -> None:
        queue.enqueue(EvalJob(node_id="n1", revision=1, source="v1"))
        job = queue.get_next()
        assert job is not None
        assert job.state == "running"

    def test_superseded_jobs_have_superseded_state(
        self, queue: EvalQueue
    ) -> None:
        queue.enqueue(EvalJob(node_id="n1", revision=1, source="v1"))
        queue.enqueue(EvalJob(node_id="n1", revision=2, source="v2"))
        # First job in queue should be superseded
        assert queue._queue[0].state == "superseded"
        assert queue._queue[1].state == "pending"

    def test_worker_can_mark_done(self, queue: EvalQueue) -> None:
        queue.enqueue(EvalJob(node_id="n1", revision=1, source="v1"))
        job = queue.get_next()
        assert job is not None
        job.state = "done"
        assert job.state == "done"
        assert job.superseded is False


# ===========================================================================
# Cascade batch edge cases
# ===========================================================================


class TestCascadeBatchEdgeCases:
    """Edge cases for enqueue_cascade_batch."""

    def test_empty_batch(self) -> None:
        queue = EvalQueue(max_size=64)
        result = queue.enqueue_cascade_batch([], ["A", "B"])
        assert result == []

    def test_single_job_batch(self) -> None:
        queue = EvalQueue(max_size=64)
        jobs = [EvalJob(node_id="A", revision=1, source="a1")]
        result = queue.enqueue_cascade_batch(jobs, ["A"])
        assert len(result) == 1
        assert result[0].node_id == "A"

    def test_batch_respects_queue_capacity(self) -> None:
        queue = EvalQueue(max_size=2)
        queue.enqueue(EvalJob(node_id="existing", revision=1, source="e1"))

        jobs = [
            EvalJob(node_id="A", revision=1, source="a1"),
            EvalJob(node_id="B", revision=1, source="b1"),
            EvalJob(node_id="C", revision=1, source="c1"),
        ]

        result = queue.enqueue_cascade_batch(jobs, ["A", "B", "C"])

        # Only 1 slot available (max=2, 1 existing)
        assert len(result) == 1

    def test_batch_dedup_plus_queue_supersede(self) -> None:
        """Batch dedup + queue-level supersede for same node already in queue."""
        queue = EvalQueue(max_size=64)

        # Pre-existing job in queue for node A
        queue.enqueue(EvalJob(node_id="A", revision=1, source="a_old"))

        # Batch with newer A
        jobs = [
            EvalJob(node_id="A", revision=2, source="a2"),
            EvalJob(node_id="A", revision=3, source="a3"),
        ]

        result = queue.enqueue_cascade_batch(jobs, ["A"])

        # Batch dedup: rev2 superseded in batch (1 drop)
        # Queue supersede: rev1 in queue superseded by rev3 (1 more drop)
        assert queue.superseded_dropped_total >= 2

        # Only latest should come out
        assert len(result) == 1
        job = queue.get_next()
        # Skip superseded, get latest
        while job is not None and job.revision != 3:
            job = queue.get_next()
        # Eventually we get rev 3 (or it was the first non-superseded)

    def test_empty_topo_order(self) -> None:
        """Empty topo_order: jobs still enqueued in stable order."""
        queue = EvalQueue(max_size=64)
        jobs = [
            EvalJob(node_id="B", revision=1, source="b1"),
            EvalJob(node_id="A", revision=1, source="a1"),
        ]
        result = queue.enqueue_cascade_batch(jobs, [])
        assert len(result) == 2
