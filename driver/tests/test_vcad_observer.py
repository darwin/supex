"""Tests for VCAD SketchUp model observer integration (Phase su-observer).

Tests the observer queue, poller, reactive watcher with pause/resume,
trigger coalescing across multiple sources, revision guards, and
stale-result protection.
"""

import time
from unittest.mock import MagicMock

import pytest

from supex_driver.connection.vcad_dag import ImportRef, VCADDag, VCADNode
from supex_driver.connection.vcad_observer import (
    VCADObserverPoller,
    VCADReactiveWatcher,
    _reset_vcad_reactive_watcher,
    get_vcad_reactive_watcher,
)
from supex_driver.connection.vcad_state import (
    RevisionTracker,
    VCADPersistentState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_path(tmp_path):
    """Temporary path for persistent state file."""
    return str(tmp_path / "vcad-state.json")


@pytest.fixture
def dag(tmp_state_path):
    """Create a fresh VCADDag with temporary state path."""
    state = VCADPersistentState(state_path=tmp_state_path)
    tracker = RevisionTracker()
    return VCADDag(state=state, tracker=tracker)


@pytest.fixture
def mock_sketchup():
    """Create a mock SketchUpConnection."""
    conn = MagicMock()
    conn.send_command.return_value = {
        "changed_entity_ids": [],
        "dropped": 0,
        "queue_size": 0,
    }
    return conn


@pytest.fixture
def poller():
    """Create a fresh VCADObserverPoller."""
    return VCADObserverPoller(poll_ms=50)


@pytest.fixture
def watcher():
    """Create a fresh VCADReactiveWatcher with fast coalescing."""
    return VCADReactiveWatcher(coalesce_ms=20)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global reactive watcher singleton between tests."""
    _reset_vcad_reactive_watcher()
    yield
    _reset_vcad_reactive_watcher()


# ---------------------------------------------------------------------------
# VCADObserverPoller: basic operations
# ---------------------------------------------------------------------------


class TestObserverPollerBasic:
    """Test basic observer poller operations."""

    def test_initial_state(self, poller):
        """Poller starts inactive."""
        assert not poller.is_polling
        assert not poller.observer_started

    def test_start_observer(self, poller, mock_sketchup):
        """start_observer calls vcad.observer_start on bridge."""
        mock_sketchup.send_command.return_value = {
            "success": True,
            "status": "started",
        }
        result = poller.start_observer(mock_sketchup)

        assert poller.observer_started
        mock_sketchup.send_command.assert_called_once_with(
            method="vcad.observer_start", params={}
        )
        assert result["success"]

    def test_stop_observer(self, poller, mock_sketchup):
        """stop_observer calls vcad.observer_stop on bridge."""
        poller._observer_started = True
        mock_sketchup.send_command.return_value = {
            "success": True,
            "status": "stopped",
        }
        poller.stop_observer(mock_sketchup)

        assert not poller.observer_started
        mock_sketchup.send_command.assert_called_once_with(
            method="vcad.observer_stop", params={}
        )

    def test_poll_once(self, poller, mock_sketchup):
        """poll_once returns entity changes from bridge."""
        mock_sketchup.send_command.return_value = {
            "changed_entity_ids": [123, 456],
            "dropped": 0,
            "queue_size": 2,
        }
        result = poller.poll_once(mock_sketchup)

        assert result["changed_entity_ids"] == [123, 456]
        assert result["dropped"] == 0
        mock_sketchup.send_command.assert_called_once_with(
            method="vcad.observer_poll", params={}
        )

    def test_poll_once_empty(self, poller, mock_sketchup):
        """poll_once returns empty when no changes."""
        result = poller.poll_once(mock_sketchup)
        assert result["changed_entity_ids"] == []


class TestObserverPollerPollingLoop:
    """Test the background polling loop."""

    def test_start_stop_polling(self, poller, mock_sketchup):
        """Polling loop starts and stops cleanly."""
        callback = MagicMock()
        poller.start_polling(mock_sketchup, callback)
        assert poller.is_polling

        time.sleep(0.1)
        poller.stop_polling()
        assert not poller.is_polling

    def test_polling_invokes_callback(self, poller, mock_sketchup):
        """Polling loop invokes callback when changes detected."""
        mock_sketchup.send_command.return_value = {
            "changed_entity_ids": [42],
            "dropped": 0,
            "queue_size": 1,
        }
        callback = MagicMock()

        poller.start_polling(mock_sketchup, callback)
        time.sleep(0.2)
        poller.stop_polling()

        assert callback.call_count >= 1
        callback.assert_called_with([42])

    def test_polling_no_callback_on_empty(self, poller, mock_sketchup):
        """Polling loop does not invoke callback when no changes."""
        mock_sketchup.send_command.return_value = {
            "changed_entity_ids": [],
            "dropped": 0,
            "queue_size": 0,
        }
        callback = MagicMock()

        poller.start_polling(mock_sketchup, callback)
        time.sleep(0.15)
        poller.stop_polling()

        callback.assert_not_called()

    def test_polling_survives_errors(self, poller, mock_sketchup):
        """Polling loop continues after connection errors."""
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("test error")
            return {"changed_entity_ids": [99], "dropped": 0, "queue_size": 1}

        mock_sketchup.send_command.side_effect = side_effect
        callback = MagicMock()

        poller.start_polling(mock_sketchup, callback)
        time.sleep(0.3)
        poller.stop_polling()

        # Should have recovered and called the callback
        assert callback.call_count >= 1

    def test_start_polling_idempotent(self, poller, mock_sketchup):
        """Starting polling twice does not create duplicate threads."""
        callback = MagicMock()
        poller.start_polling(mock_sketchup, callback)
        thread1 = poller._thread
        poller.start_polling(mock_sketchup, callback)
        thread2 = poller._thread

        assert thread1 is thread2
        poller.stop_polling()


# ---------------------------------------------------------------------------
# VCADReactiveWatcher: pause/resume
# ---------------------------------------------------------------------------


class TestReactiveWatcherPauseResume:
    """Test pause/resume (batch mode) functionality."""

    def test_initial_state(self, watcher):
        """Watcher starts unpaused and unreconciled."""
        assert not watcher.is_paused
        assert not watcher.is_reconciled

    def test_pause(self, watcher):
        """Pause sets paused state."""
        result = watcher.pause()
        assert watcher.is_paused
        assert result["status"] == "paused"

    def test_pause_idempotent(self, watcher):
        """Pausing while already paused returns already_paused."""
        watcher.pause()
        result = watcher.pause()
        assert result["status"] == "already_paused"

    def test_resume_when_not_paused(self, watcher):
        """Resuming when not paused returns already_running."""
        result = watcher.resume()
        assert result["status"] == "already_running"
        assert result["flushed"] == 0

    def test_pause_accumulates_changes(self, watcher):
        """Changes during pause accumulate in pending set."""
        watcher.mark_reconciled()
        watcher.pause()

        watcher.trigger("node-a", "fs-watch")
        watcher.trigger("node-b", "mod-track")
        watcher.trigger("node-a", "su-observer")  # duplicate

        pending = watcher.pending_while_paused
        assert pending == {"node-a", "node-b"}

    def test_resume_flushes_accumulated(self, watcher):
        """Resume flushes all accumulated changes."""
        triggered_nodes: list[set[str]] = []
        watcher.set_cascade_callback(lambda nodes: triggered_nodes.append(nodes))
        watcher.mark_reconciled()

        watcher.pause()
        watcher.trigger("node-a", "fs-watch")
        watcher.trigger("node-b", "mod-track")

        result = watcher.resume()
        assert result["status"] == "resumed"
        assert result["flushed"] == 2
        assert not watcher.is_paused

        # Wait for coalescer to fire
        time.sleep(0.1)
        assert len(triggered_nodes) >= 1
        flushed = set()
        for batch in triggered_nodes:
            flushed.update(batch)
        assert "node-a" in flushed
        assert "node-b" in flushed

    def test_resume_empty(self, watcher):
        """Resume with no accumulated changes."""
        watcher.mark_reconciled()
        watcher.pause()
        result = watcher.resume()
        assert result["flushed"] == 0


# ---------------------------------------------------------------------------
# VCADReactiveWatcher: trigger flow
# ---------------------------------------------------------------------------


class TestReactiveWatcherTrigger:
    """Test the unified trigger flow."""

    def test_trigger_before_reconciliation_ignored(self, watcher):
        """Events before reconciliation are silently ignored."""
        triggered = []
        watcher.set_cascade_callback(lambda nodes: triggered.append(nodes))

        watcher.trigger("node-x", "fs-watch")
        time.sleep(0.1)
        assert len(triggered) == 0

    def test_trigger_after_reconciliation(self, watcher):
        """Events after reconciliation feed into coalescer."""
        triggered: list[set[str]] = []
        watcher.set_cascade_callback(lambda nodes: triggered.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger("node-a", "fs-watch")
        time.sleep(0.1)

        assert len(triggered) >= 1
        assert "node-a" in triggered[0]

    def test_trigger_many(self, watcher):
        """trigger_many feeds multiple nodes into coalescer."""
        triggered: list[set[str]] = []
        watcher.set_cascade_callback(lambda nodes: triggered.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger_many(["node-a", "node-b", "node-c"], "manual")
        time.sleep(0.1)

        assert len(triggered) >= 1
        all_triggered = set()
        for batch in triggered:
            all_triggered.update(batch)
        assert all_triggered == {"node-a", "node-b", "node-c"}


# ---------------------------------------------------------------------------
# Coalescing: multi-source within one window
# ---------------------------------------------------------------------------


class TestCoalescingMultiSource:
    """Test that events from different sources coalesce into one cascade."""

    def test_multi_source_coalesced(self, watcher):
        """fs-watch + mod-track + su-observer within one window -> one cascade."""
        triggered: list[set[str]] = []
        watcher.set_cascade_callback(lambda nodes: triggered.append(nodes))
        watcher.mark_reconciled()

        # Rapid events from different sources
        watcher.trigger("node-a", "fs-watch")
        watcher.trigger("node-b", "mod-track")
        watcher.trigger("node-c", "su-observer")

        time.sleep(0.1)

        # Should produce exactly one cascade with all three
        assert len(triggered) == 1
        assert triggered[0] == {"node-a", "node-b", "node-c"}

    def test_duplicate_node_deduplicated(self, watcher):
        """Same node from different sources produces one entry."""
        triggered: list[set[str]] = []
        watcher.set_cascade_callback(lambda nodes: triggered.append(nodes))
        watcher.mark_reconciled()

        watcher.trigger("node-a", "fs-watch")
        watcher.trigger("node-a", "mod-track")
        watcher.trigger("node-a", "su-observer")

        time.sleep(0.1)

        assert len(triggered) == 1
        assert triggered[0] == {"node-a"}

    def test_continuous_stream_bounded_batches(self, watcher):
        """Continuous change stream executes bounded batches, no starvation."""
        triggered: list[set[str]] = []

        def slow_callback(nodes: set[str]) -> None:
            triggered.append(nodes)
            time.sleep(0.03)  # Simulate cascade work

        watcher.set_cascade_callback(slow_callback)
        watcher.mark_reconciled()

        # Stream events over time
        for i in range(10):
            watcher.trigger(f"node-{i}", "fs-watch")
            time.sleep(0.01)

        # Wait for all cascades to complete
        time.sleep(0.5)

        # Should have at least 1 cascade but bounded batches
        assert len(triggered) >= 1
        # All nodes should have been covered
        all_triggered = set()
        for batch in triggered:
            all_triggered.update(batch)
        assert len(all_triggered) == 10


# ---------------------------------------------------------------------------
# Storm/dedup check: rapid entity changes
# ---------------------------------------------------------------------------


class TestStormDedup:
    """Test deduplication of rapid entity changes within poll windows."""

    def test_rapid_entity_changes_deduplicated(self, dag, watcher):
        """Multiple rapid edits to same entity produce one cascade."""
        # Setup: node-a imports entity:12345
        node_a = VCADNode(
            node_id="node-a",
            source_file="/project/part-a.cmp.oo",
            imports=[ImportRef(
                binding_name="table_dims",
                selector="entity:12345",
                extracts=["dims"],
            )],
        )
        dag.add_node(node_a)

        triggered: list[set[str]] = []
        watcher.set_cascade_callback(lambda nodes: triggered.append(nodes))
        watcher.mark_reconciled()

        # Simulate observer poll returning same entity multiple times
        # (as if entity was modified rapidly)
        entity_ids = [12345, 12345, 12345]  # Same entity, 3 times
        affected_nodes = set()
        for eid in entity_ids:
            dependents = dag.get_dependents_of_entity(str(eid))
            affected_nodes.update(dependents)

        # Should only have node-a once despite 3 raw events
        assert affected_nodes == {"node-a"}

        watcher.trigger_many(list(affected_nodes), "su-observer")
        time.sleep(0.1)

        # One cascade with one node
        assert len(triggered) == 1
        assert triggered[0] == {"node-a"}


# ---------------------------------------------------------------------------
# Stale-result race check
# ---------------------------------------------------------------------------


class TestStaleResultRace:
    """Test that stale eval results are dropped via revision guard."""

    def test_stale_revision_dropped(self, dag):
        """Older revision result is rejected when newer revision exists."""
        node = VCADNode(node_id="node-a", source_file="/project/part-a.cmp.oo")
        dag.add_node(node)

        # Bump revision twice (simulating two rapid updates)
        rev1 = dag.bump_revision("node-a")
        rev2 = dag.bump_revision("node-a")

        assert rev1 == 1
        assert rev2 == 2

        # rev1 is now stale
        assert not dag.should_apply("node-a", rev1)
        assert dag.tracker.stale_dropped == 1

        # rev2 is current
        assert dag.should_apply("node-a", rev2)

    def test_only_latest_revision_applied(self, dag):
        """Only the result from the latest revision is applied."""
        node = VCADNode(node_id="node-a", source_file="/project/part-a.cmp.oo")
        dag.add_node(node)

        rev1 = dag.bump_revision("node-a")
        rev2 = dag.bump_revision("node-a")

        # Simulate: older eval finishes first (rev1), should be dropped
        assert not dag.should_apply("node-a", rev1)

        # Newer eval finishes (rev2), should be applied
        assert dag.should_apply("node-a", rev2)
        dag.mark_applied("node-a", rev2)

        updated = dag.get_node("node-a")
        assert updated is not None
        assert updated.applied_revision == rev2

    def test_stale_drop_counter_increments(self, dag):
        """Stale dropped counter increments for each stale result."""
        node = VCADNode(node_id="node-a", source_file="/project/part-a.cmp.oo")
        dag.add_node(node)

        dag.bump_revision("node-a")
        rev2 = dag.bump_revision("node-a")
        rev3 = dag.bump_revision("node-a")

        # rev1 and rev2 are both stale
        dag.should_apply("node-a", 1)  # stale
        dag.should_apply("node-a", rev2)  # stale
        assert dag.tracker.stale_dropped == 2

        # rev3 is current
        assert dag.should_apply("node-a", rev3)
        assert dag.tracker.stale_dropped == 2  # unchanged


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test global singleton management."""

    def test_get_returns_same_instance(self):
        """Singleton returns same instance."""
        w1 = get_vcad_reactive_watcher()
        w2 = get_vcad_reactive_watcher()
        assert w1 is w2

    def test_reset_creates_new_instance(self):
        """Reset creates new instance on next access."""
        w1 = get_vcad_reactive_watcher()
        _reset_vcad_reactive_watcher()
        w2 = get_vcad_reactive_watcher()
        assert w1 is not w2
