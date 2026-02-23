"""Mock-based integration tests for VCAD observer + batch mode (Phase su-observer).

Tests the full flow: observer polling -> DAG lookup -> trigger coalescing
-> cascade execution, with mocked SketchUp bridge and sidecar connections.
Also tests batch mode (pause/resume) with multi-file edits.
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from supex_driver.connection.vcad_dag import ImportRef, VCADDag, VCADNode
from supex_driver.connection.vcad_observer import (
    VCADReactiveWatcher,
    _reset_vcad_reactive_watcher,
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
def mock_vcad():
    """Create a mock VCADConnection."""
    conn = MagicMock()
    conn.eval_file.return_value = {"mesh_path": "/tmp/out.dae"}
    conn.watch_poll.return_value = {"changes": []}
    conn.get_affected_nodes.return_value = []
    return conn


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global reactive watcher singleton between tests."""
    _reset_vcad_reactive_watcher()
    yield
    _reset_vcad_reactive_watcher()


# ---------------------------------------------------------------------------
# Observer -> DAG -> Cascade flow
# ---------------------------------------------------------------------------


class TestObserverDagCascadeFlow:
    """Test end-to-end: entity change -> DAG lookup -> cascade."""

    def test_entity_change_triggers_dependent_nodes(self, dag):
        """Entity change triggers all nodes that import that entity."""
        # Setup: two nodes import from entity:100
        dag.add_node(VCADNode(
            node_id="bracket",
            source_file="/project/bracket.cmp.oo",
            imports=[ImportRef(
                binding_name="table_dims",
                selector="entity:100",
                extracts=["dims"],
            )],
        ))
        dag.add_node(VCADNode(
            node_id="plate",
            source_file="/project/plate.cmp.oo",
            imports=[ImportRef(
                binding_name="table_bbox",
                selector="entity:100",
                extracts=["bbox"],
            )],
        ))
        # This node does NOT import entity:100
        dag.add_node(VCADNode(
            node_id="bolt",
            source_file="/project/bolt.cmp.oo",
        ))

        # Simulate observer poll returning entity 100
        dependents = dag.get_dependents_of_entity("100")
        assert set(dependents) == {"bracket", "plate"}

    def test_observer_poll_to_cascade(self, dag, mock_sketchup):
        """Full flow: poll -> DAG lookup -> coalesced cascade."""
        # Setup DAG
        dag.add_node(VCADNode(
            node_id="node-a",
            source_file="/project/a.cmp.oo",
            imports=[ImportRef(
                binding_name="dims",
                selector="entity:42",
                extracts=["dims"],
            )],
        ))

        # Setup reactive watcher
        cascade_results: list[set[str]] = []
        watcher = VCADReactiveWatcher(coalesce_ms=20)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        # Simulate what the observer poll loop would do
        poll_result = {
            "changed_entity_ids": [42],
            "dropped": 0,
            "queue_size": 1,
        }

        # Look up affected nodes
        for eid in poll_result["changed_entity_ids"]:
            affected = dag.get_dependents_of_entity(str(eid))
            watcher.trigger_many(affected, "su-observer")

        time.sleep(0.1)

        assert len(cascade_results) >= 1
        assert "node-a" in cascade_results[0]

    def test_downstream_cascade_ordering(self, dag):
        """Downstream dependents are evaluated in topological order."""
        # A -> B -> C (dependency chain)
        dag.add_node(VCADNode(
            node_id="A",
            source_file="/project/a.cmp.oo",
        ))
        dag.add_node(VCADNode(
            node_id="B",
            source_file="/project/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a_solid",
                selector="entity:1",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="C",
            source_file="/project/c.cmp.oo",
            imports=[ImportRef(
                binding_name="b_solid",
                selector="entity:2",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="B",
            )],
        ))

        # When A changes, B and C are downstream
        downstream = dag.get_downstream("A")
        assert set(downstream) == {"B", "C"}

        # Topological order respects dependencies
        affected = ["A"] + downstream
        order = dag._topological_sort(affected)
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")


# ---------------------------------------------------------------------------
# Multi-source coalescing
# ---------------------------------------------------------------------------


class TestMultiSourceCoalescing:
    """Test coalescing events from fs-watch, mod-track, and su-observer."""

    def test_all_three_sources_coalesced(self, dag):
        """fs-watch + mod-track + su-observer within one window -> one cascade."""
        dag.add_node(VCADNode(
            node_id="node-fs",
            source_file="/project/fs.cmp.oo",
        ))
        dag.add_node(VCADNode(
            node_id="node-mod",
            source_file="/project/mod.cmp.oo",
        ))
        dag.add_node(VCADNode(
            node_id="node-obs",
            source_file="/project/obs.cmp.oo",
            imports=[ImportRef(
                binding_name="x",
                selector="entity:50",
                extracts=["dims"],
            )],
        ))

        cascade_results: list[set[str]] = []
        watcher = VCADReactiveWatcher(coalesce_ms=30)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        # Simulate all three sources within one coalescing window
        watcher.trigger("node-fs", "fs-watch")
        watcher.trigger("node-mod", "mod-track")
        watcher.trigger("node-obs", "su-observer")

        time.sleep(0.15)

        # One cascade covering all three
        assert len(cascade_results) == 1
        assert cascade_results[0] == {"node-fs", "node-mod", "node-obs"}

    def test_events_during_cascade_deferred(self, dag):
        """Events arriving during an active cascade are deferred to next batch."""
        cascade_results: list[set[str]] = []
        cascade_event = threading.Event()

        def slow_cascade(nodes: set[str]) -> None:
            cascade_results.append(nodes)
            cascade_event.set()
            time.sleep(0.08)  # Simulate slow cascade

        watcher = VCADReactiveWatcher(coalesce_ms=10)
        watcher.set_cascade_callback(slow_cascade)
        watcher.mark_reconciled()

        # Trigger first cascade
        watcher.trigger("node-a", "fs-watch")

        # Wait for first cascade to start
        cascade_event.wait(timeout=1.0)
        cascade_event.clear()

        # Trigger during active cascade
        watcher.trigger("node-b", "su-observer")

        # Wait for deferred cascade
        time.sleep(0.3)

        assert len(cascade_results) >= 2
        assert "node-a" in cascade_results[0]
        # node-b was deferred to second cascade
        deferred = set()
        for batch in cascade_results[1:]:
            deferred.update(batch)
        assert "node-b" in deferred


# ---------------------------------------------------------------------------
# Batch mode (pause/resume) workflow
# ---------------------------------------------------------------------------


class TestBatchModeWorkflow:
    """Test typical agent batch workflow: pause -> edit -> resume."""

    def test_agent_batch_workflow(self):
        """Full agent workflow: pause, edit 3 files, resume -> one cascade."""
        cascade_results: list[set[str]] = []
        watcher = VCADReactiveWatcher(coalesce_ms=20)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        # 1. Agent pauses
        pause_result = watcher.pause()
        assert pause_result["status"] == "paused"

        # 2. Agent edits multiple files (triggers arrive from fs-watch)
        watcher.trigger("dims-node", "fs-watch")      # dims.oo
        watcher.trigger("bracket-node", "fs-watch")    # bracket.cmp.oo
        watcher.trigger("plate-node", "fs-watch")      # plate.cmp.oo

        # No cascade during pause
        time.sleep(0.1)
        assert len(cascade_results) == 0

        # 3. Agent resumes
        resume_result = watcher.resume()
        assert resume_result["status"] == "resumed"
        assert resume_result["flushed"] == 3

        # Wait for cascade
        time.sleep(0.1)

        # One cascade covering all three
        assert len(cascade_results) >= 1
        all_triggered = set()
        for batch in cascade_results:
            all_triggered.update(batch)
        assert all_triggered == {"dims-node", "bracket-node", "plate-node"}

    def test_batch_mode_deduplicates(self):
        """Duplicate events during pause are deduplicated on resume."""
        cascade_results: list[set[str]] = []
        watcher = VCADReactiveWatcher(coalesce_ms=20)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        watcher.pause()

        # Same node triggered multiple times during pause
        watcher.trigger("node-a", "fs-watch")
        watcher.trigger("node-a", "mod-track")
        watcher.trigger("node-a", "su-observer")
        watcher.trigger("node-b", "fs-watch")

        result = watcher.resume()
        assert result["flushed"] == 2  # Only 2 unique nodes

        time.sleep(0.1)

        assert len(cascade_results) >= 1
        all_triggered = set()
        for batch in cascade_results:
            all_triggered.update(batch)
        assert all_triggered == {"node-a", "node-b"}

    def test_no_cascade_between_pause_resume(self):
        """No cascades fire between pause and resume."""
        cascade_count = 0

        def counting_callback(nodes: set[str]) -> None:
            nonlocal cascade_count
            cascade_count += 1

        watcher = VCADReactiveWatcher(coalesce_ms=10)
        watcher.set_cascade_callback(counting_callback)
        watcher.mark_reconciled()

        watcher.pause()
        for i in range(5):
            watcher.trigger(f"node-{i}", "fs-watch")
            time.sleep(0.02)

        # Should be zero cascades
        assert cascade_count == 0

        watcher.resume()
        time.sleep(0.15)

        # Exactly one cascade after resume
        assert cascade_count == 1


# ---------------------------------------------------------------------------
# Stale-result race with two updates
# ---------------------------------------------------------------------------


class TestStaleResultRaceIntegration:
    """Test stale-result protection in cascade context."""

    def test_two_updates_only_newer_applied(self, dag):
        """Two rapid updates for same node: only newer revision wins."""
        dag.add_node(VCADNode(
            node_id="widget",
            source_file="/project/widget.cmp.oo",
        ))

        # Simulate two rapid file edits
        rev1 = dag.bump_revision("widget")
        rev2 = dag.bump_revision("widget")

        # Older eval completes first (would happen if eval1 was slower)
        assert not dag.should_apply("widget", rev1)
        assert dag.tracker.stale_dropped == 1

        # Newer eval completes
        assert dag.should_apply("widget", rev2)
        dag.mark_applied("widget", rev2)

        node = dag.get_node("widget")
        assert node is not None
        assert node.applied_revision == rev2
        assert node.revision == rev2

    def test_stale_drop_logged(self, dag):
        """Stale drops increment the counter for monitoring."""
        dag.add_node(VCADNode(
            node_id="node-x",
            source_file="/project/x.cmp.oo",
        ))

        # Generate 3 revisions, only apply the last
        dag.bump_revision("node-x")  # rev 1
        dag.bump_revision("node-x")  # rev 2
        rev3 = dag.bump_revision("node-x")  # rev 3

        # Try to apply stale revisions
        dag.should_apply("node-x", 1)
        dag.should_apply("node-x", 2)

        assert dag.tracker.stale_dropped == 2

        # Apply current
        assert dag.should_apply("node-x", rev3)
        dag.mark_applied("node-x", rev3)

    def test_cascade_with_revision_guard(self, dag):
        """Cascade respects revision guard: bumps before eval, checks before apply."""
        dag.add_node(VCADNode(
            node_id="part-a",
            source_file="/project/part-a.cmp.oo",
        ))
        dag.add_node(VCADNode(
            node_id="part-b",
            source_file="/project/part-b.cmp.oo",
            imports=[ImportRef(
                binding_name="a_solid",
                selector="entity:1",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="part-a",
            )],
        ))

        # Cascade: part-a -> part-b
        affected = ["part-a", "part-b"]
        order = dag._topological_sort(affected)
        assert order == ["part-a", "part-b"]

        # Bump revisions before eval
        revisions = {}
        for nid in order:
            revisions[nid] = dag.bump_revision(nid)

        # Both should be applicable
        assert dag.should_apply("part-a", revisions["part-a"])
        assert dag.should_apply("part-b", revisions["part-b"])

        # Apply both
        dag.mark_applied("part-a", revisions["part-a"])
        dag.mark_applied("part-b", revisions["part-b"])

        assert dag.get_node("part-a").applied_revision == 1
        assert dag.get_node("part-b").applied_revision == 1


# ---------------------------------------------------------------------------
# Observer + batch mode combined
# ---------------------------------------------------------------------------


class TestObserverBatchCombined:
    """Test observer changes during batch mode."""

    def test_observer_changes_during_pause(self, dag):
        """Entity changes during pause are accumulated and flushed on resume."""
        dag.add_node(VCADNode(
            node_id="panel",
            source_file="/project/panel.cmp.oo",
            imports=[ImportRef(
                binding_name="frame_dims",
                selector="entity:200",
                extracts=["dims"],
            )],
        ))

        cascade_results: list[set[str]] = []
        watcher = VCADReactiveWatcher(coalesce_ms=20)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        # Pause
        watcher.pause()

        # Simulate observer detecting entity change during pause
        dependents = dag.get_dependents_of_entity("200")
        watcher.trigger_many(dependents, "su-observer")

        # Also simulate fs-watch change during pause
        watcher.trigger("panel", "fs-watch")

        # No cascade during pause
        assert len(cascade_results) == 0

        # Resume
        watcher.resume()
        time.sleep(0.1)

        # One cascade with panel (deduplicated from both sources)
        assert len(cascade_results) >= 1
        all_triggered = set()
        for batch in cascade_results:
            all_triggered.update(batch)
        assert "panel" in all_triggered

    def test_mixed_sources_during_pause(self, dag):
        """All three sources during pause -> one cascade on resume."""
        dag.add_node(VCADNode(
            node_id="bracket",
            source_file="/project/bracket.cmp.oo",
            imports=[ImportRef(
                binding_name="plate_dims",
                selector="entity:300",
                extracts=["dims"],
            )],
        ))
        dag.add_node(VCADNode(
            node_id="plate",
            source_file="/project/plate.cmp.oo",
        ))

        cascade_results: list[set[str]] = []
        watcher = VCADReactiveWatcher(coalesce_ms=20)
        watcher.set_cascade_callback(lambda nodes: cascade_results.append(nodes))
        watcher.mark_reconciled()

        watcher.pause()

        # su-observer change affects bracket
        dependents = dag.get_dependents_of_entity("300")
        watcher.trigger_many(dependents, "su-observer")

        # fs-watch change to plate
        watcher.trigger("plate", "fs-watch")

        # Resume -> one cascade
        watcher.resume()
        time.sleep(0.1)

        assert len(cascade_results) >= 1
        all_triggered = set()
        for batch in cascade_results:
            all_triggered.update(batch)
        assert all_triggered == {"bracket", "plate"}
