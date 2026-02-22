"""Tests for multi-source trigger coalescing window (Phase trigger-coalescing).

Covers:
- Multi-source burst: fs-watch/mod-track/su-observer events within one window
  produce exactly one cascade over the unioned affected nodes.
- Active-cascade deferral: events injected during a running cascade run in the
  next batch only (no parallel cascade execution).
- Starvation bound: sustained long event stream produces bounded flush intervals
  and forward progress (all nodes eventually cascade).
- Telemetry: coalesce_batches_total, coalesce_merged_events_total, and
  coalesce_window_ms_effective are emitted correctly.
"""

import threading
import time

import pytest

from supex_driver.connection.vcad_metrics import (
    VcadMetrics,
    _reset_vcad_metrics,
    get_vcad_metrics,
)
from supex_driver.connection.vcad_observer import (
    VcadReactiveWatcher,
    _reset_vcad_reactive_watcher,
)
from supex_driver.connection.vcad_state import TriggerCoalescer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset global singletons between tests."""
    _reset_vcad_metrics()
    _reset_vcad_reactive_watcher()
    yield
    _reset_vcad_metrics()
    _reset_vcad_reactive_watcher()


# ===========================================================================
# Multi-source burst check
# ===========================================================================


class TestMultiSourceBurst:
    """Emit fs-watch/mod-track/observer events in one window,
    verify one cascade over unioned affected nodes."""

    def test_three_sources_one_cascade(self):
        """Events from all three sources within one window -> one cascade."""
        cascade_results: list[set[str]] = []
        watcher = VcadReactiveWatcher(coalesce_ms=30)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger("node-fs", "fs-watch")
        watcher.trigger("node-mod", "mod-track")
        watcher.trigger("node-obs", "su-observer")

        time.sleep(0.15)

        assert len(cascade_results) == 1
        assert cascade_results[0] == {"node-fs", "node-mod", "node-obs"}

    def test_four_sources_one_cascade(self):
        """All four sources (incl. manual) merge into one cascade."""
        cascade_results: list[set[str]] = []
        watcher = VcadReactiveWatcher(coalesce_ms=30)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger("a", "fs-watch")
        watcher.trigger("b", "mod-track")
        watcher.trigger("c", "su-observer")
        watcher.trigger("d", "manual")

        time.sleep(0.15)

        assert len(cascade_results) == 1
        assert cascade_results[0] == {"a", "b", "c", "d"}

    def test_duplicate_node_across_sources_deduplicated(self):
        """Same node from different sources produces one entry in cascade."""
        cascade_results: list[set[str]] = []
        watcher = VcadReactiveWatcher(coalesce_ms=30)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger("shared-node", "fs-watch")
        watcher.trigger("shared-node", "mod-track")
        watcher.trigger("shared-node", "su-observer")
        watcher.trigger("other-node", "manual")

        time.sleep(0.15)

        assert len(cascade_results) == 1
        assert cascade_results[0] == {"shared-node", "other-node"}

    def test_trigger_many_coalesces(self):
        """trigger_many merges into same coalescing window."""
        cascade_results: list[set[str]] = []
        watcher = VcadReactiveWatcher(coalesce_ms=30)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger_many(["a", "b"], "fs-watch")
        watcher.trigger_many(["c", "d"], "mod-track")
        watcher.trigger("e", "su-observer")

        time.sleep(0.15)

        assert len(cascade_results) == 1
        assert cascade_results[0] == {"a", "b", "c", "d", "e"}

    def test_union_of_affected_nodes(self):
        """Node set is the union of all sources' affected nodes."""
        cascade_results: list[set[str]] = []
        coalescer = TriggerCoalescer(
            coalesce_ms=20,
            callback=lambda nodes: cascade_results.append(nodes),
        )

        # Simulate different sources reporting different sets of affected nodes
        coalescer.trigger("bracket", "fs-watch")
        coalescer.trigger("plate", "mod-track")
        coalescer.trigger("bracket", "su-observer")  # duplicate
        coalescer.trigger("bolt", "manual")

        time.sleep(0.1)

        assert len(cascade_results) == 1
        assert cascade_results[0] == {"bracket", "plate", "bolt"}

    def test_events_before_reconciliation_ignored(self):
        """Events before reconciliation do not trigger cascades."""
        cascade_results: list[set[str]] = []
        watcher = VcadReactiveWatcher(coalesce_ms=20)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        # NOT calling mark_reconciled()

        watcher.trigger("node-a", "fs-watch")
        watcher.trigger("node-b", "mod-track")

        time.sleep(0.1)
        assert len(cascade_results) == 0


# ===========================================================================
# Active-cascade deferral check
# ===========================================================================


class TestActiveCascadeDeferral:
    """Inject events during running cascade, verify they run in next batch
    only (no parallel cascade)."""

    def test_events_during_cascade_deferred(self):
        """Events during an active cascade go into the next batch."""
        cascade_results: list[set[str]] = []
        cascade_started = threading.Event()

        def slow_cascade(nodes: set[str]) -> None:
            cascade_results.append(nodes)
            cascade_started.set()
            time.sleep(0.1)  # Simulate work

        coalescer = TriggerCoalescer(coalesce_ms=10, callback=slow_cascade)

        # Trigger first cascade
        coalescer.trigger("node-a", "fs-watch")

        # Wait for cascade to start executing
        cascade_started.wait(timeout=1.0)
        cascade_started.clear()

        # Inject events during active cascade
        coalescer.trigger("node-b", "su-observer")
        coalescer.trigger("node-c", "mod-track")

        # Wait for deferred cascade to complete
        time.sleep(0.4)

        assert len(cascade_results) >= 2
        assert cascade_results[0] == {"node-a"}
        # Deferred events appear in subsequent batch(es)
        deferred_nodes: set[str] = set()
        for batch in cascade_results[1:]:
            deferred_nodes.update(batch)
        assert "node-b" in deferred_nodes
        assert "node-c" in deferred_nodes

    def test_no_parallel_cascade_execution(self):
        """Only one cascade runs at a time — verify serialization."""
        active_count = 0
        max_active = 0
        lock = threading.Lock()
        cascade_results: list[set[str]] = []
        first_started = threading.Event()

        def cascade_fn(nodes: set[str]) -> None:
            nonlocal active_count, max_active
            with lock:
                active_count += 1
                max_active = max(max_active, active_count)
            cascade_results.append(nodes)
            first_started.set()
            time.sleep(0.05)
            with lock:
                active_count -= 1

        coalescer = TriggerCoalescer(coalesce_ms=10, callback=cascade_fn)

        coalescer.trigger("a", "fs-watch")
        first_started.wait(timeout=1.0)

        # Inject during active cascade
        coalescer.trigger("b", "mod-track")
        coalescer.trigger("c", "su-observer")

        time.sleep(0.4)

        # Never more than one cascade active at once
        assert max_active == 1
        # All nodes processed
        all_nodes: set[str] = set()
        for batch in cascade_results:
            all_nodes.update(batch)
        assert all_nodes == {"a", "b", "c"}

    def test_deferred_events_combined_in_one_batch(self):
        """Multiple deferred events merge into one next batch."""
        cascade_results: list[set[str]] = []
        cascade_started = threading.Event()

        def slow_cascade(nodes: set[str]) -> None:
            cascade_results.append(nodes)
            cascade_started.set()
            time.sleep(0.08)

        coalescer = TriggerCoalescer(coalesce_ms=10, callback=slow_cascade)

        coalescer.trigger("root", "manual")
        cascade_started.wait(timeout=1.0)
        cascade_started.clear()

        # Multiple deferred events during active cascade
        coalescer.trigger("d1", "fs-watch")
        coalescer.trigger("d2", "mod-track")
        coalescer.trigger("d3", "su-observer")

        time.sleep(0.4)

        assert len(cascade_results) >= 2
        assert cascade_results[0] == {"root"}
        # All deferred events should appear in exactly one subsequent batch
        assert cascade_results[1] == {"d1", "d2", "d3"}

    def test_cascade_callback_error_still_processes_deferred(self):
        """If the cascade callback raises, deferred events still fire next."""
        cascade_results: list[set[str]] = []
        call_count = 0

        def failing_then_ok(nodes: set[str]) -> None:
            nonlocal call_count
            call_count += 1
            cascade_results.append(nodes)
            if call_count == 1:
                raise RuntimeError("simulated cascade error")

        coalescer = TriggerCoalescer(coalesce_ms=10, callback=failing_then_ok)

        coalescer.trigger("a", "fs-watch")
        time.sleep(0.05)

        # Trigger during/after failed cascade
        coalescer.trigger("b", "mod-track")
        time.sleep(0.2)

        # Both batches executed despite first failure
        assert len(cascade_results) >= 2
        all_nodes: set[str] = set()
        for batch in cascade_results:
            all_nodes.update(batch)
        assert all_nodes == {"a", "b"}


# ===========================================================================
# Starvation bound check
# ===========================================================================


class TestStarvationBound:
    """Sustain long event stream and verify bounded flush intervals +
    forward progress."""

    def test_continuous_stream_makes_forward_progress(self):
        """Events arriving faster than coalesce window still produce cascades."""
        cascade_results: list[set[str]] = []
        coalescer = TriggerCoalescer(
            coalesce_ms=50,
            max_coalesce_ms=100,
            callback=lambda nodes: cascade_results.append(nodes),
        )

        # Stream events every 20ms for 500ms
        # Without bounded wait, the 50ms timer keeps resetting and never fires
        for i in range(25):
            coalescer.trigger(f"node-{i}", "fs-watch")
            time.sleep(0.02)

        # Wait for final flush
        time.sleep(0.2)

        # Must have produced at least 2 cascades (forward progress)
        assert len(cascade_results) >= 2

        # All 25 nodes must be covered
        all_nodes: set[str] = set()
        for batch in cascade_results:
            all_nodes.update(batch)
        assert len(all_nodes) == 25

    def test_bounded_flush_fires_within_max_window(self):
        """Bounded wait cap forces a flush even under continuous stream."""
        flush_times: list[float] = []
        start = time.monotonic()

        def track_cascade(nodes: set[str]) -> None:
            flush_times.append(time.monotonic() - start)

        coalescer = TriggerCoalescer(
            coalesce_ms=50,
            max_coalesce_ms=120,
            callback=track_cascade,
        )

        # Stream events every 10ms for 600ms — coalesce_ms=50 would never
        # fire without bounded wait since each trigger resets the timer
        for i in range(60):
            coalescer.trigger(f"n-{i}", "fs-watch")
            time.sleep(0.01)

        time.sleep(0.15)

        # With max_coalesce_ms=120ms, we expect flushes roughly every
        # 120ms, so in ~600ms we should have at least 3 flushes
        assert len(flush_times) >= 3

    def test_all_nodes_eventually_cascade(self):
        """Every node in a sustained stream eventually appears in a cascade."""
        all_cascaded: set[str] = set()
        lock = threading.Lock()

        def collect_cascade(nodes: set[str]) -> None:
            with lock:
                all_cascaded.update(nodes)

        coalescer = TriggerCoalescer(
            coalesce_ms=30,
            max_coalesce_ms=80,
            callback=collect_cascade,
        )

        total_nodes = 50
        for i in range(total_nodes):
            coalescer.trigger(f"node-{i}", "fs-watch")
            time.sleep(0.005)

        # Wait for all cascades to finish
        time.sleep(0.3)

        with lock:
            assert len(all_cascaded) == total_nodes

    def test_bounded_flush_with_mixed_sources(self):
        """Bounded flush works correctly with interleaved sources."""
        cascade_results: list[set[str]] = []
        sources = ["fs-watch", "mod-track", "su-observer", "manual"]

        coalescer = TriggerCoalescer(
            coalesce_ms=40,
            max_coalesce_ms=100,
            callback=lambda nodes: cascade_results.append(nodes),
        )

        # Interleave sources in rapid stream
        for i in range(40):
            src = sources[i % len(sources)]
            coalescer.trigger(f"node-{i}", src)
            time.sleep(0.008)

        time.sleep(0.2)

        # Forward progress: multiple batches
        assert len(cascade_results) >= 2

        # Complete coverage
        all_nodes: set[str] = set()
        for batch in cascade_results:
            all_nodes.update(batch)
        assert len(all_nodes) == 40

    def test_starvation_bound_with_reactive_watcher(self):
        """Bounded flush through VcadReactiveWatcher integration."""
        cascade_results: list[set[str]] = []
        watcher = VcadReactiveWatcher(coalesce_ms=40)
        # Set max_coalesce_ms on the underlying coalescer
        watcher.coalescer.max_coalesce_ms = 100
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        for i in range(30):
            src = ["fs-watch", "mod-track", "su-observer"][i % 3]
            watcher.trigger(f"node-{i}", src)
            time.sleep(0.01)

        time.sleep(0.3)

        # Must have multiple cascades (bounded flush prevents starvation)
        assert len(cascade_results) >= 2

        all_nodes: set[str] = set()
        for batch in cascade_results:
            all_nodes.update(batch)
        assert len(all_nodes) == 30


# ===========================================================================
# Telemetry contract
# ===========================================================================


class TestCoalescingTelemetry:
    """Verify coalesce telemetry counters and gauge."""

    def test_coalesce_batches_total_incremented(self):
        """coalesce_batches_total increments per executed coalesced batch."""
        metrics = get_vcad_metrics()
        fired = threading.Event()

        coalescer = TriggerCoalescer(
            coalesce_ms=10,
            callback=lambda nodes: fired.set(),
        )
        coalescer.trigger("a", "fs-watch")
        coalescer.trigger("b", "mod-track")
        coalescer.trigger("c", "su-observer")

        fired.wait(timeout=2.0)
        time.sleep(0.05)

        assert metrics.get_counter("coalesce_batches_total") == 1
        assert coalescer.cascade_count == 1

    def test_coalesce_merged_events_total_incremented(self):
        """coalesce_merged_events_total counts each source event."""
        metrics = get_vcad_metrics()
        fired = threading.Event()

        coalescer = TriggerCoalescer(
            coalesce_ms=10,
            callback=lambda nodes: fired.set(),
        )
        coalescer.trigger("a", "fs-watch")
        coalescer.trigger("b", "mod-track")
        coalescer.trigger("a", "su-observer")  # duplicate node, still counted

        fired.wait(timeout=2.0)
        time.sleep(0.05)

        assert metrics.get_counter("coalesce_merged_events_total") == 3
        assert coalescer.merged_events_total == 3

    def test_coalesce_window_ms_effective_published(self):
        """coalesce_window_ms_effective gauge is set on construction."""
        metrics = get_vcad_metrics()
        TriggerCoalescer(coalesce_ms=42.0)
        assert metrics.get_gauge("coalesce_window_ms_effective") == 42.0

    def test_coalesce_window_ms_effective_in_snapshot(self):
        """coalesce_window_ms_effective appears in metrics snapshot."""
        metrics = get_vcad_metrics()
        TriggerCoalescer(coalesce_ms=200.0)
        snap = metrics.snapshot()
        assert snap["coalesce_window_ms_effective"] == 200.0

    def test_multiple_batches_accumulate_counters(self):
        """Counters accumulate across multiple cascade batches."""
        metrics = get_vcad_metrics()
        batch_count = 0
        batch_event = threading.Event()

        def counting_callback(nodes: set[str]) -> None:
            nonlocal batch_count
            batch_count += 1
            batch_event.set()

        coalescer = TriggerCoalescer(coalesce_ms=10, callback=counting_callback)

        # First batch
        coalescer.trigger("x", "fs-watch")
        batch_event.wait(timeout=1.0)
        time.sleep(0.05)
        batch_event.clear()

        # Second batch
        coalescer.trigger("y", "mod-track")
        batch_event.wait(timeout=1.0)
        time.sleep(0.05)

        assert metrics.get_counter("coalesce_batches_total") == 2
        assert metrics.get_counter("coalesce_merged_events_total") == 2

    def test_deferred_events_counted_in_merged_total(self):
        """Events deferred during cascade still count in merged_events_total."""
        metrics = get_vcad_metrics()
        cascade_started = threading.Event()

        def slow_cascade(nodes: set[str]) -> None:
            cascade_started.set()
            time.sleep(0.08)

        coalescer = TriggerCoalescer(coalesce_ms=10, callback=slow_cascade)

        coalescer.trigger("a", "fs-watch")
        cascade_started.wait(timeout=1.0)

        # These are deferred but still count as merged events
        coalescer.trigger("b", "mod-track")
        coalescer.trigger("c", "su-observer")

        time.sleep(0.3)

        assert metrics.get_counter("coalesce_merged_events_total") == 3
        assert coalescer.merged_events_total == 3
