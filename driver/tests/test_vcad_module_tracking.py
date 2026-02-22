"""Tests for VCAD module tracking (Phase mod-track).

Tests the module tracking system that tracks which .loon library files each
vcad node depends on via [use ...]. When a shared library file changes,
all affected nodes are identified for cascade re-evaluation.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from supex_driver.connection.vcad_dag import VcadDag, VcadNode
from supex_driver.connection.vcad_file_watcher import (
    VcadFileWatcher,
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
    """Create a fresh VcadDag with temporary state path."""
    state = VCADPersistentState(state_path=tmp_state_path)
    tracker = RevisionTracker()
    return VcadDag(state=state, tracker=tracker)


@pytest.fixture
def watcher():
    """Create a fresh VcadFileWatcher instance."""
    return VcadFileWatcher()


@pytest.fixture
def mock_vcad():
    """Create a mock VCADConnection."""
    conn = MagicMock()
    conn.watch_start.return_value = {"status": "watching", "dir": "/project"}
    conn.watch_stop.return_value = {"status": "stopped"}
    conn.watch_poll.return_value = {"changes": []}
    conn.get_affected_nodes.return_value = []
    conn.eval_file.return_value = {"obj_path": "/tmp/out.dae"}
    return conn


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global file watcher singleton between tests."""
    _reset_vcad_file_watcher()
    yield
    _reset_vcad_file_watcher()


# ---------------------------------------------------------------------------
# VCADConnection.eval_file with node_id
# ---------------------------------------------------------------------------


class TestEvalFileWithNodeId:
    """Test VCADConnection.eval_file passes node_id to sidecar."""

    def test_eval_file_without_node_id(self):
        """eval_file without node_id sends only path."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"obj_path": "/tmp/out.dae", "volume": 1000.0}
        )

        result = conn.eval_file("/project/test.skp.oo")

        conn.send_command.assert_called_once_with(
            "vcad.eval_file", {"path": "/project/test.skp.oo"}
        )
        assert result["obj_path"] == "/tmp/out.dae"

    def test_eval_file_with_node_id(self):
        """eval_file with node_id sends both path and node_id."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={
                "obj_path": "/tmp/out.dae",
                "volume": 1000.0,
                "loaded_module_paths": ["/project/src/dims.loon"],
            }
        )

        result = conn.eval_file("/project/test.skp.oo", node_id="bracket")

        conn.send_command.assert_called_once_with(
            "vcad.eval_file",
            {"path": "/project/test.skp.oo", "node_id": "bracket"},
        )
        assert result["loaded_module_paths"] == ["/project/src/dims.loon"]

    def test_eval_file_node_id_none_omitted(self):
        """eval_file with node_id=None does not include it in params."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"obj_path": "/tmp/out.dae"}
        )

        conn.eval_file("/project/test.skp.oo", node_id=None)

        args = conn.send_command.call_args
        params = args[0][1]
        assert "node_id" not in params


# ---------------------------------------------------------------------------
# VCADConnection.get_affected_nodes
# ---------------------------------------------------------------------------


class TestGetAffectedNodes:
    """Test VCADConnection.get_affected_nodes."""

    def test_get_affected_nodes(self):
        """get_affected_nodes sends correct command."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"node_ids": ["bracket", "base-plate"]}
        )

        result = conn.get_affected_nodes("/project/src/dims.loon")

        conn.send_command.assert_called_once_with(
            "vcad.get_affected_nodes",
            {"path": "/project/src/dims.loon"},
        )
        assert result == ["bracket", "base-plate"]

    def test_get_affected_nodes_empty(self):
        """get_affected_nodes returns empty list when no nodes affected."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={"node_ids": []})

        result = conn.get_affected_nodes("/project/src/unused.loon")

        assert result == []

    def test_get_affected_nodes_missing_key(self):
        """get_affected_nodes handles missing node_ids key gracefully."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={})

        result = conn.get_affected_nodes("/project/src/dims.loon")

        assert result == []


# ---------------------------------------------------------------------------
# VcadFileWatcher.find_nodes_for_loon_changes
# ---------------------------------------------------------------------------


class TestFindNodesForLoonChanges:
    """Test matching .loon library changes to affected nodes via module tracker."""

    def test_loon_change_finds_affected_nodes(self, watcher, mock_vcad):
        """Loon change queries sidecar for affected nodes."""
        mock_vcad.get_affected_nodes.return_value = ["bracket", "base-plate"]

        changes = [{"path": "/project/src/dims.loon", "kind": "loon"}]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        mock_vcad.get_affected_nodes.assert_called_once_with(
            "/project/src/dims.loon"
        )
        assert set(affected) == {"bracket", "base-plate"}

    def test_ignores_vcad_loon_changes(self, watcher, mock_vcad):
        """Only processes loon changes, not vcad_loon (.skp.oo) changes."""
        changes = [
            {"path": "/project/test.skp.oo", "kind": "vcad_loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == []
        mock_vcad.get_affected_nodes.assert_not_called()

    def test_multiple_loon_changes_deduplicated(self, watcher, mock_vcad):
        """Multiple .loon changes are deduplicated by node_id."""
        mock_vcad.get_affected_nodes.side_effect = [
            ["bracket", "base-plate"],  # dims.loon affects these
            ["bracket"],  # helpers.loon also affects bracket
        ]

        changes = [
            {"path": "/project/src/dims.loon", "kind": "loon"},
            {"path": "/project/src/helpers.loon", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert set(affected) == {"bracket", "base-plate"}
        assert mock_vcad.get_affected_nodes.call_count == 2

    def test_no_affected_nodes(self, watcher, mock_vcad):
        """Returns empty list when no nodes depend on changed file."""
        mock_vcad.get_affected_nodes.return_value = []

        changes = [{"path": "/project/src/unused.loon", "kind": "loon"}]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == []

    def test_empty_changes(self, watcher, mock_vcad):
        """Empty change list returns empty result."""
        affected = watcher.find_nodes_for_loon_changes([], mock_vcad)

        assert affected == []
        mock_vcad.get_affected_nodes.assert_not_called()

    def test_connection_error_handled(self, watcher, mock_vcad):
        """Connection errors are logged and swallowed."""
        mock_vcad.get_affected_nodes.side_effect = Exception("Connection lost")

        changes = [{"path": "/project/src/dims.loon", "kind": "loon"}]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        # Should not raise, returns empty
        assert affected == []

    def test_empty_path_skipped(self, watcher, mock_vcad):
        """Changes with empty path are skipped."""
        changes = [{"path": "", "kind": "loon"}]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == []
        mock_vcad.get_affected_nodes.assert_not_called()

    def test_mixed_changes(self, watcher, mock_vcad):
        """Mixed vcad_loon and loon changes: only loon processed."""
        mock_vcad.get_affected_nodes.return_value = ["bracket"]

        changes = [
            {"path": "/project/test.skp.oo", "kind": "vcad_loon"},
            {"path": "/project/src/dims.loon", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == ["bracket"]
        # Only called for the .loon change
        mock_vcad.get_affected_nodes.assert_called_once_with(
            "/project/src/dims.loon"
        )


# ---------------------------------------------------------------------------
# Integration: vcad_place passes node_id to eval_file
# ---------------------------------------------------------------------------


class TestVcadPlaceModuleTracking:
    """Test that vcad_place passes node_id for module tracking."""

    def test_vcad_place_passes_node_id(self, tmp_path):
        """vcad_place passes node_id to eval_file for module tracking."""
        from supex_driver.mcp.vcad_tools import (
            vcad_place,
            _reset_vcad_dag,
        )

        _reset_vcad_dag()

        source_file = str(tmp_path / "test.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")

        mock_ctx = MagicMock()
        mock_ctx.request_id = "test-req-1"

        with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get_vcad, \
             patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get_su, \
             patch("supex_driver.mcp.vcad_tools.get_vcad_file_watcher") as mock_get_watcher:

            mock_vcad = MagicMock()
            mock_vcad.eval_file.return_value = {
                "obj_path": "/tmp/out.dae",
                "loaded_module_paths": ["/project/src/dims.loon"],
            }
            mock_get_vcad.return_value = mock_vcad

            mock_su = MagicMock()
            mock_su.send_command.return_value = {
                "success": True,
                "node_id": "test-node",
                "entity_id": 42,
            }
            mock_get_su.return_value = mock_su

            mock_watcher = MagicMock()
            mock_get_watcher.return_value = mock_watcher

            result_str = vcad_place(mock_ctx, "test-node", source_file)
            result = json.loads(result_str)

            assert result["success"]
            # Verify eval_file was called with node_id
            mock_vcad.eval_file.assert_called_once_with(
                source_file, node_id="test-node"
            )

        _reset_vcad_dag()


# ---------------------------------------------------------------------------
# Integration: _vcad_update_single passes node_id
# ---------------------------------------------------------------------------


class TestVcadUpdateSingleModuleTracking:
    """Test that _vcad_update_single passes node_id for module tracking."""

    def test_update_single_passes_node_id(self, dag, tmp_path):
        """_vcad_update_single passes node_id to eval_file."""
        from supex_driver.mcp.vcad_tools import _vcad_update_single

        source_file = str(tmp_path / "bracket.skp.oo")
        dag.add_node(VcadNode(
            node_id="bracket",
            source_file=source_file,
        ))

        mock_ctx = MagicMock()
        mock_ctx.request_id = "test-req-1"

        with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get_vcad, \
             patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get_su:

            mock_vcad = MagicMock()
            mock_vcad.eval_file.return_value = {
                "obj_path": "/tmp/out.dae",
                "loaded_module_paths": [],
            }
            mock_get_vcad.return_value = mock_vcad

            mock_su = MagicMock()
            mock_su.send_command.return_value = {
                "success": True,
                "entity_id": 42,
            }
            mock_get_su.return_value = mock_su

            revision = dag.bump_revision("bracket")
            result = _vcad_update_single(
                mock_ctx, "bracket", source_file, revision, dag
            )

            assert result["success"]
            mock_vcad.eval_file.assert_called_once_with(
                source_file, node_id="bracket"
            )


# ---------------------------------------------------------------------------
# Integration: vcad_update passes node_id
# ---------------------------------------------------------------------------


class TestVcadUpdateModuleTracking:
    """Test that vcad_update passes node_id for module tracking."""

    def test_vcad_update_passes_node_id(self, tmp_path):
        """vcad_update passes node_id to eval_file."""
        from supex_driver.mcp.vcad_tools import (
            vcad_update,
            _reset_vcad_dag,
            get_vcad_dag,
        )

        _reset_vcad_dag()
        dag = get_vcad_dag()

        source_file = str(tmp_path / "bracket.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")

        mock_ctx = MagicMock()
        mock_ctx.request_id = "test-req-1"

        with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get_vcad, \
             patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get_su:

            mock_vcad = MagicMock()
            mock_vcad.eval_file.return_value = {
                "obj_path": "/tmp/out.dae",
                "loaded_module_paths": ["/project/src/dims.loon"],
            }
            mock_get_vcad.return_value = mock_vcad

            mock_su = MagicMock()
            mock_su.send_command.return_value = {
                "success": True,
                "entity_id": 42,
            }
            mock_get_su.return_value = mock_su

            result_str = vcad_update(
                mock_ctx, "bracket", source_file=source_file
            )
            result = json.loads(result_str)

            assert result["success"]
            mock_vcad.eval_file.assert_called_once_with(
                source_file, node_id="bracket"
            )

        _reset_vcad_dag()


# ---------------------------------------------------------------------------
# End-to-end: .loon change -> find affected -> cascade
# ---------------------------------------------------------------------------


class TestLoonChangeCascadeFlow:
    """Test end-to-end: .loon change detected -> affected nodes found -> cascade."""

    def test_loon_change_cascade_flow(self, dag, tmp_path):
        """Full flow: .loon change -> module tracker -> cascade update."""
        source_a = str(tmp_path / "base-plate.skp.oo")
        source_b = str(tmp_path / "bracket.skp.oo")

        dag.add_node(VcadNode(node_id="base-plate", source_file=source_a))
        dag.add_node(VcadNode(node_id="bracket", source_file=source_b))

        watcher = VcadFileWatcher()

        # Simulate sidecar returning affected nodes for dims.loon change
        mock_vcad = MagicMock()
        mock_vcad.get_affected_nodes.return_value = [
            "base-plate", "bracket"
        ]

        changes = [
            {"path": "/project/src/dims.loon", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert set(affected) == {"base-plate", "bracket"}

        # Each affected node would trigger vcad_update_cascade
        for node_id in affected:
            node = dag.get_node(node_id)
            assert node is not None

    def test_mixed_changes_flow(self, dag, tmp_path):
        """Mixed .skp.oo and .loon changes handled separately."""
        source_a = str(tmp_path / "base-plate.skp.oo")
        source_b = str(tmp_path / "bracket.skp.oo")

        dag.add_node(VcadNode(node_id="base-plate", source_file=source_a))
        dag.add_node(VcadNode(node_id="bracket", source_file=source_b))

        watcher = VcadFileWatcher()

        # Setup mock
        mock_vcad = MagicMock()
        mock_vcad.get_affected_nodes.return_value = ["bracket"]

        changes = [
            # Direct .skp.oo change
            {"path": source_a, "kind": "vcad_loon"},
            # Library .loon change
            {"path": "/project/src/helpers.loon", "kind": "loon"},
        ]

        # .skp.oo changes: find direct node matches
        skp_oo_nodes = watcher.find_nodes_for_changes(changes, dag)
        assert skp_oo_nodes == ["base-plate"]

        # .loon changes: find affected via module tracker
        loon_nodes = watcher.find_nodes_for_loon_changes(changes, mock_vcad)
        assert loon_nodes == ["bracket"]

        # Combined: all affected nodes (deduplicated)
        all_affected = set(skp_oo_nodes) | set(loon_nodes)
        assert all_affected == {"base-plate", "bracket"}

    def test_loon_change_no_affected_nodes(self, dag, tmp_path):
        """Loon change with no affected nodes produces no cascades."""
        source = str(tmp_path / "base-plate.skp.oo")
        dag.add_node(VcadNode(node_id="base-plate", source_file=source))

        watcher = VcadFileWatcher()

        mock_vcad = MagicMock()
        mock_vcad.get_affected_nodes.return_value = []

        changes = [
            {"path": "/project/src/unused.loon", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == []
