"""Tests for VCAD filesystem watcher integration (Phase fs-watch)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from supex_driver.connection.vcad_dag import VCADDag, VCADNode, ImportRef
from supex_driver.connection.vcad_file_watcher import (
    VCADFileWatcher,
    _detect_project_root,
    get_vcad_file_watcher,
    _reset_vcad_file_watcher,
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
def watcher():
    """Create a fresh VCADFileWatcher instance."""
    return VCADFileWatcher()


@pytest.fixture
def mock_vcad():
    """Create a mock VCADConnection."""
    conn = MagicMock()
    conn.watch_start.return_value = {"status": "watching", "dir": "/project"}
    conn.watch_stop.return_value = {"status": "stopped"}
    conn.watch_poll.return_value = {"changes": []}
    return conn


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global file watcher singleton between tests."""
    _reset_vcad_file_watcher()
    yield
    _reset_vcad_file_watcher()


# ---------------------------------------------------------------------------
# VCADFileWatcher basic lifecycle
# ---------------------------------------------------------------------------


class TestVCADFileWatcherLifecycle:
    """Test basic watcher lifecycle operations."""

    def test_initial_state(self, watcher):
        """Watcher starts inactive."""
        assert not watcher.is_watching
        assert watcher.watch_dir is None

    def test_start(self, watcher, mock_vcad):
        """Start sets watch_dir and calls sidecar."""
        result = watcher.start("/project", mock_vcad)

        assert watcher.is_watching
        assert watcher.watch_dir == "/project"
        assert result["status"] == "watching"
        mock_vcad.watch_start.assert_called_once_with("/project")

    def test_stop(self, watcher, mock_vcad):
        """Stop clears watch_dir and calls sidecar."""
        watcher.start("/project", mock_vcad)

        result = watcher.stop(mock_vcad)

        assert not watcher.is_watching
        assert watcher.watch_dir is None
        assert result["status"] == "stopped"
        mock_vcad.watch_stop.assert_called_once()

    def test_poll_empty(self, watcher, mock_vcad):
        """Poll returns empty list when no changes."""
        changes = watcher.poll(mock_vcad)
        assert changes == []
        mock_vcad.watch_poll.assert_called_once()

    def test_poll_with_changes(self, watcher, mock_vcad):
        """Poll returns change list from sidecar."""
        mock_vcad.watch_poll.return_value = {
            "changes": [
                {"path": "/project/test.skp.oo", "kind": "vcad_loon"},
                {"path": "/project/src/lib.oo", "kind": "loon"},
            ]
        }

        changes = watcher.poll(mock_vcad)

        assert len(changes) == 2
        assert changes[0]["path"] == "/project/test.skp.oo"
        assert changes[0]["kind"] == "vcad_loon"
        assert changes[1]["kind"] == "loon"


# ---------------------------------------------------------------------------
# Auto-start
# ---------------------------------------------------------------------------


class TestVCADFileWatcherAutoStart:
    """Test auto-start behavior triggered from vcad_place."""

    def test_auto_start_from_source_file(self, watcher, mock_vcad, tmp_path):
        """Auto-start detects project root from source file."""
        source_file = str(tmp_path / "test.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")

        watcher.auto_start_if_needed(source_file, mock_vcad)

        assert watcher.is_watching
        assert watcher.watch_dir == str(tmp_path)
        mock_vcad.watch_start.assert_called_once_with(str(tmp_path))

    def test_auto_start_idempotent(self, watcher, mock_vcad, tmp_path):
        """Auto-start does not re-start if already watching."""
        source_file = str(tmp_path / "test.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")

        watcher.auto_start_if_needed(source_file, mock_vcad)
        watcher.auto_start_if_needed(source_file, mock_vcad)

        # Only started once
        mock_vcad.watch_start.assert_called_once()

    def test_auto_start_handles_error(self, watcher, mock_vcad, tmp_path):
        """Auto-start swallows errors gracefully."""
        source_file = str(tmp_path / "test.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")

        mock_vcad.watch_start.side_effect = Exception("Connection lost")

        # Should not raise
        watcher.auto_start_if_needed(source_file, mock_vcad)
        assert not watcher.is_watching


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


class TestProjectRootDetection:
    """Test project root detection from source file paths."""

    def test_detect_from_file(self, tmp_path):
        """Detects parent directory of source file."""
        source = str(tmp_path / "bracket.skp.oo")
        with open(source, "w") as f:
            f.write("")

        root = _detect_project_root(source)
        assert root == str(tmp_path)

    def test_detect_from_nested_file(self, tmp_path):
        """Detects parent directory even for nested files."""
        subdir = tmp_path / "parts"
        subdir.mkdir()
        source = str(subdir / "bracket.skp.oo")
        with open(source, "w") as f:
            f.write("")

        root = _detect_project_root(source)
        assert root == str(subdir)

    def test_detect_from_nonexistent_dir(self):
        """Returns None for nonexistent directory."""
        root = _detect_project_root("/nonexistent/path/file.skp.oo")
        assert root is None


# ---------------------------------------------------------------------------
# find_nodes_for_changes
# ---------------------------------------------------------------------------


class TestFindNodesForChanges:
    """Test matching changed paths to DAG nodes."""

    def test_match_by_source_file(self, watcher, dag, tmp_path):
        """Finds node whose source_file matches changed path."""
        source = str(tmp_path / "bracket.skp.oo")
        dag.add_node(VCADNode(
            node_id="bracket",
            source_file=source,
        ))

        changes = [{"path": source, "kind": "vcad_loon"}]
        node_ids = watcher.find_nodes_for_changes(changes, dag)

        assert node_ids == ["bracket"]

    def test_no_match(self, watcher, dag, tmp_path):
        """Returns empty list when no node matches."""
        dag.add_node(VCADNode(
            node_id="bracket",
            source_file=str(tmp_path / "bracket.skp.oo"),
        ))

        changes = [{"path": str(tmp_path / "other.skp.oo"), "kind": "vcad_loon"}]
        node_ids = watcher.find_nodes_for_changes(changes, dag)

        assert node_ids == []

    def test_ignores_loon_changes(self, watcher, dag, tmp_path):
        """Only matches vcad_loon changes, not loon library changes."""
        source = str(tmp_path / "lib.oo")
        dag.add_node(VCADNode(
            node_id="lib",
            source_file=source,
        ))

        changes = [{"path": source, "kind": "loon"}]
        node_ids = watcher.find_nodes_for_changes(changes, dag)

        assert node_ids == []

    def test_multiple_matches(self, watcher, dag, tmp_path):
        """Finds multiple nodes when multiple files change."""
        source_a = str(tmp_path / "a.skp.oo")
        source_b = str(tmp_path / "b.skp.oo")
        dag.add_node(VCADNode(node_id="node-a", source_file=source_a))
        dag.add_node(VCADNode(node_id="node-b", source_file=source_b))

        changes = [
            {"path": source_a, "kind": "vcad_loon"},
            {"path": source_b, "kind": "vcad_loon"},
        ]
        node_ids = watcher.find_nodes_for_changes(changes, dag)

        assert set(node_ids) == {"node-a", "node-b"}

    def test_empty_changes(self, watcher, dag):
        """Empty change list returns empty result."""
        assert watcher.find_nodes_for_changes([], dag) == []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestVCADFileWatcherSingleton:
    """Test global singleton management."""

    def test_get_returns_same_instance(self):
        """get_vcad_file_watcher returns same instance."""
        w1 = get_vcad_file_watcher()
        w2 = get_vcad_file_watcher()
        assert w1 is w2

    def test_reset_clears_singleton(self):
        """_reset_vcad_file_watcher creates fresh instance."""
        w1 = get_vcad_file_watcher()
        _reset_vcad_file_watcher()
        w2 = get_vcad_file_watcher()
        assert w1 is not w2


# ---------------------------------------------------------------------------
# VCADConnection watch methods
# ---------------------------------------------------------------------------


class TestVCADConnectionWatchMethods:
    """Test VCADConnection convenience methods for watch operations."""

    def test_watch_start(self):
        """watch_start sends vcad.watch_start command."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"status": "watching", "dir": "/project"}
        )

        result = conn.watch_start("/project")

        conn.send_command.assert_called_once_with(
            "vcad.watch_start", {"dir": "/project"}
        )
        assert result["status"] == "watching"

    def test_watch_stop(self):
        """watch_stop sends vcad.watch_stop command."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={"status": "stopped"})

        result = conn.watch_stop()

        conn.send_command.assert_called_once_with("vcad.watch_stop", {})
        assert result["status"] == "stopped"

    def test_watch_poll(self):
        """watch_poll sends vcad.watch_poll command."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={"changes": []})

        result = conn.watch_poll()

        conn.send_command.assert_called_once_with("vcad.watch_poll", {})
        assert result["changes"] == []


# ---------------------------------------------------------------------------
# Integration: vcad_place triggers auto-start
# ---------------------------------------------------------------------------


class TestVCADPlaceAutoStart:
    """Test that vcad_place auto-starts the file watcher."""

    def test_vcad_place_auto_starts_watcher(self, tmp_path):
        """vcad_place calls auto_start_if_needed after DAG registration."""
        from supex_driver.mcp.vcad_tools import (
            vcad_place,
            _reset_vcad_dag,
            _reset_vcad_file_watcher,
        )

        _reset_vcad_dag()
        _reset_vcad_file_watcher()

        source_file = str(tmp_path / "test.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")

        mock_ctx = MagicMock()
        mock_ctx.request_id = "test-req-1"

        with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get_vcad, \
             patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get_su, \
             patch("supex_driver.mcp.vcad_tools.get_vcad_file_watcher") as mock_get_watcher:

            mock_vcad = MagicMock()
            mock_vcad.eval_file.return_value = {"mesh_path": "/tmp/out.dae"}
            mock_get_vcad.return_value = mock_vcad

            mock_su = MagicMock()
            mock_su.send_command.return_value = {
                "success": True,
                "node_id": "test",
                "entity_id": 42,
            }
            mock_get_su.return_value = mock_su

            mock_watcher = MagicMock()
            mock_get_watcher.return_value = mock_watcher

            result_str = vcad_place(
                mock_ctx, "test", source_file
            )
            result = json.loads(result_str)

            assert result["success"]
            mock_watcher.auto_start_if_needed.assert_called_once_with(
                source_file, mock_vcad
            )

        _reset_vcad_dag()
        _reset_vcad_file_watcher()


# ---------------------------------------------------------------------------
# Integration: poll + cascade
# ---------------------------------------------------------------------------


class TestPollAndCascade:
    """Test the poll -> find_nodes -> cascade flow."""

    def test_poll_finds_changed_nodes_and_cascade(self, dag, tmp_path):
        """End-to-end: poll changes, find nodes, trigger cascade."""
        source_a = str(tmp_path / "a.skp.oo")
        source_b = str(tmp_path / "b.skp.oo")

        dag.add_node(VCADNode(node_id="node-a", source_file=source_a))
        dag.add_node(VCADNode(
            node_id="node-b",
            source_file=source_b,
            imports=[ImportRef(
                binding_name="a_solid",
                selector="entity:100",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="node-a",
            )],
        ))

        watcher = VCADFileWatcher()

        # Simulate sidecar returning a change for source_a
        changes = [{"path": source_a, "kind": "vcad_loon"}]
        changed_nodes = watcher.find_nodes_for_changes(changes, dag)

        assert changed_nodes == ["node-a"]

        # Verify cascade would include downstream
        downstream = dag.get_downstream("node-a")
        assert "node-b" in downstream

        # Verify topological order
        affected = ["node-a"] + downstream
        order = dag._topological_sort(affected)
        assert order.index("node-a") < order.index("node-b")

    def test_poll_no_changes_no_cascade(self, dag, tmp_path):
        """No changes means no cascade needed."""
        source = str(tmp_path / "a.skp.oo")
        dag.add_node(VCADNode(node_id="node-a", source_file=source))

        watcher = VCADFileWatcher()
        changed_nodes = watcher.find_nodes_for_changes([], dag)
        assert changed_nodes == []

    def test_poll_change_to_leaf_node_no_downstream(self, dag, tmp_path):
        """Change to a leaf node has no downstream cascade."""
        source_a = str(tmp_path / "a.skp.oo")
        source_b = str(tmp_path / "b.skp.oo")

        dag.add_node(VCADNode(node_id="node-a", source_file=source_a))
        dag.add_node(VCADNode(
            node_id="node-b",
            source_file=source_b,
            imports=[ImportRef(
                binding_name="a_solid",
                selector="entity:100",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="node-a",
            )],
        ))

        watcher = VCADFileWatcher()
        changes = [{"path": source_b, "kind": "vcad_loon"}]
        changed_nodes = watcher.find_nodes_for_changes(changes, dag)

        assert changed_nodes == ["node-b"]
        downstream = dag.get_downstream("node-b")
        assert downstream == []
