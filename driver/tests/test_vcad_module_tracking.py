"""Tests for VCAD module tracking (Phase mod-track).

Tests the module tracking system that tracks which .oo library files each
vcad node depends on via [use ...]. When a shared library file changes,
all affected nodes are identified for cascade re-evaluation.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from supex_driver.connection.vcad_dag import VCADDag, VCADNode
from supex_driver.connection.vcad_file_watcher import (
    VCADFileWatcher,
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
    conn.get_affected_nodes.return_value = []
    conn.eval_with_imports.return_value = {
        "mesh_path": "/tmp/out.dae",
        "loaded_module_paths": [],
    }
    return conn


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global file watcher singleton between tests."""
    _reset_vcad_file_watcher()
    yield
    _reset_vcad_file_watcher()


# ---------------------------------------------------------------------------
# VCADConnection.eval_with_imports
# ---------------------------------------------------------------------------


class TestEvalWithImports:
    """Test VCADConnection.eval_with_imports passes correct params to sidecar."""

    def test_eval_with_imports_defaults(self):
        """eval_with_imports with defaults sends transformed_source and export_mesh."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"mesh_path": "/tmp/out.dae", "volume": 1000.0}
        )

        result = conn.eval_with_imports("[cube 10.0 10.0 10.0]")

        conn.send_command.assert_called_once_with(
            "vcad.eval_with_imports",
            {"transformed_source": "[cube 10.0 10.0 10.0]"},
        )
        assert result["mesh_path"] == "/tmp/out.dae"

    def test_eval_with_imports_with_node_id(self):
        """eval_with_imports with node_id includes it in params."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={
                "mesh_path": "/tmp/out.dae",
                "volume": 1000.0,
                "loaded_module_paths": ["/project/src/dims.oo"],
            }
        )

        result = conn.eval_with_imports(
            "[cube 10.0 10.0 10.0]",
            node_id="bracket",
            cache_adt=True,
            track_modules=True,
        )

        conn.send_command.assert_called_once_with(
            "vcad.eval_with_imports",
            {
                "transformed_source": "[cube 10.0 10.0 10.0]",
                "node_id": "bracket",
                "cache_adt": True,
                "track_modules": True,
            },
        )
        assert result["loaded_module_paths"] == ["/project/src/dims.oo"]

    def test_eval_with_imports_node_id_none_omitted(self):
        """eval_with_imports with node_id=None does not include it in params."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"mesh_path": "/tmp/out.dae"}
        )

        conn.eval_with_imports("[cube 10.0 10.0 10.0]", node_id=None)

        args = conn.send_command.call_args
        params = args[0][1]
        assert "node_id" not in params

    def test_eval_with_imports_all_flags(self):
        """eval_with_imports with all flags set includes them in params."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(
            return_value={"mesh_path": "/tmp/out.dae"}
        )

        conn.eval_with_imports(
            "[cube 10.0 10.0 10.0]",
            base_dir="/project",
            imports={"imp_1": {"data": "test"}},
            node_id="bracket",
            display=True,
            cache_adt=True,
            track_modules=True,
            inspect=True,
            export_mesh=False,
        )

        conn.send_command.assert_called_once_with(
            "vcad.eval_with_imports",
            {
                "transformed_source": "[cube 10.0 10.0 10.0]",
                "base_dir": "/project",
                "imports": {"imp_1": {"data": "test"}},
                "node_id": "bracket",
                "display": True,
                "cache_adt": True,
                "track_modules": True,
                "inspect": True,
                "export_mesh": False,
            },
        )


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

        result = conn.get_affected_nodes("/project/src/dims.oo")

        conn.send_command.assert_called_once_with(
            "vcad.get_affected_nodes",
            {"path": "/project/src/dims.oo"},
        )
        assert result == ["bracket", "base-plate"]

    def test_get_affected_nodes_empty(self):
        """get_affected_nodes returns empty list when no nodes affected."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={"node_ids": []})

        result = conn.get_affected_nodes("/project/src/unused.oo")

        assert result == []

    def test_get_affected_nodes_missing_key(self):
        """get_affected_nodes handles missing node_ids key gracefully."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={})

        result = conn.get_affected_nodes("/project/src/dims.oo")

        assert result == []


# ---------------------------------------------------------------------------
# VCADFileWatcher.find_nodes_for_loon_changes
# ---------------------------------------------------------------------------


class TestFindNodesForLoonChanges:
    """Test matching .oo library changes to affected nodes via module tracker."""

    def test_loon_change_finds_affected_nodes(self, watcher, mock_vcad):
        """Loon change queries sidecar for affected nodes."""
        mock_vcad.get_affected_nodes.return_value = ["bracket", "base-plate"]

        changes = [{"path": "/project/src/dims.oo", "kind": "loon"}]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        mock_vcad.get_affected_nodes.assert_called_once_with(
            "/project/src/dims.oo"
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
        """Multiple .oo changes are deduplicated by node_id."""
        mock_vcad.get_affected_nodes.side_effect = [
            ["bracket", "base-plate"],  # dims.oo affects these
            ["bracket"],  # helpers.oo also affects bracket
        ]

        changes = [
            {"path": "/project/src/dims.oo", "kind": "loon"},
            {"path": "/project/src/helpers.oo", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert set(affected) == {"bracket", "base-plate"}
        assert mock_vcad.get_affected_nodes.call_count == 2

    def test_no_affected_nodes(self, watcher, mock_vcad):
        """Returns empty list when no nodes depend on changed file."""
        mock_vcad.get_affected_nodes.return_value = []

        changes = [{"path": "/project/src/unused.oo", "kind": "loon"}]
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

        changes = [{"path": "/project/src/dims.oo", "kind": "loon"}]
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
            {"path": "/project/src/dims.oo", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == ["bracket"]
        # Only called for the .oo module change
        mock_vcad.get_affected_nodes.assert_called_once_with(
            "/project/src/dims.oo"
        )


# ---------------------------------------------------------------------------
# Integration: vcad_place passes node_id to eval_with_imports
# ---------------------------------------------------------------------------


class TestVCADPlaceModuleTracking:
    """Test that vcad_place passes node_id for module tracking."""

    def test_vcad_place_passes_node_id(self, tmp_path):
        """vcad_place passes node_id to eval_with_imports for module tracking."""
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
            mock_vcad.eval_with_imports.return_value = {
                "mesh_path": "/tmp/out.dae",
                "loaded_module_paths": ["/project/src/dims.oo"],
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
            # Verify eval_with_imports was called with node_id and correct flags
            mock_vcad.eval_with_imports.assert_called_once()
            call_kwargs = mock_vcad.eval_with_imports.call_args
            assert call_kwargs.kwargs["node_id"] == "test-node"
            assert call_kwargs.kwargs["cache_adt"] is True
            assert call_kwargs.kwargs["track_modules"] is True
            assert call_kwargs.kwargs["export_mesh"] is True

        _reset_vcad_dag()


# ---------------------------------------------------------------------------
# Integration: _vcad_update_single passes node_id
# ---------------------------------------------------------------------------


class TestVCADUpdateSingleModuleTracking:
    """Test that _vcad_update_single passes node_id for module tracking."""

    def test_update_single_passes_node_id(self, dag, tmp_path):
        """_vcad_update_single passes node_id to eval_with_imports."""
        from supex_driver.mcp.vcad_tools import _vcad_update_single

        source_file = str(tmp_path / "bracket.skp.oo")
        with open(source_file, "w") as f:
            f.write("[cube 10.0 10.0 10.0]")
        dag.add_node(VCADNode(
            node_id="bracket",
            source_file=source_file,
        ))

        mock_ctx = MagicMock()
        mock_ctx.request_id = "test-req-1"

        with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get_vcad, \
             patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get_su:

            mock_vcad = MagicMock()
            mock_vcad.eval_with_imports.return_value = {
                "mesh_path": "/tmp/out.dae",
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
            mock_vcad.eval_with_imports.assert_called_once()
            call_kwargs = mock_vcad.eval_with_imports.call_args
            assert call_kwargs.kwargs["node_id"] == "bracket"
            assert call_kwargs.kwargs["cache_adt"] is True
            assert call_kwargs.kwargs["track_modules"] is True
            assert call_kwargs.kwargs["export_mesh"] is True


# ---------------------------------------------------------------------------
# Integration: vcad_update passes node_id
# ---------------------------------------------------------------------------


class TestVCADUpdateModuleTracking:
    """Test that vcad_update passes node_id for module tracking."""

    def test_vcad_update_passes_node_id(self, tmp_path):
        """vcad_update passes node_id to eval_with_imports."""
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
            mock_vcad.eval_with_imports.return_value = {
                "mesh_path": "/tmp/out.dae",
                "loaded_module_paths": ["/project/src/dims.oo"],
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
            mock_vcad.eval_with_imports.assert_called_once()
            call_kwargs = mock_vcad.eval_with_imports.call_args
            assert call_kwargs.kwargs["node_id"] == "bracket"
            assert call_kwargs.kwargs["cache_adt"] is True
            assert call_kwargs.kwargs["track_modules"] is True
            assert call_kwargs.kwargs["export_mesh"] is True

        _reset_vcad_dag()


# ---------------------------------------------------------------------------
# End-to-end: .oo change -> find affected -> cascade
# ---------------------------------------------------------------------------


class TestLoonChangeCascadeFlow:
    """Test end-to-end: .oo change detected -> affected nodes found -> cascade."""

    def test_loon_change_cascade_flow(self, dag, tmp_path):
        """Full flow: .oo change -> module tracker -> cascade update."""
        source_a = str(tmp_path / "base-plate.skp.oo")
        source_b = str(tmp_path / "bracket.skp.oo")

        dag.add_node(VCADNode(node_id="base-plate", source_file=source_a))
        dag.add_node(VCADNode(node_id="bracket", source_file=source_b))

        watcher = VCADFileWatcher()

        # Simulate sidecar returning affected nodes for dims.oo change
        mock_vcad = MagicMock()
        mock_vcad.get_affected_nodes.return_value = [
            "base-plate", "bracket"
        ]

        changes = [
            {"path": "/project/src/dims.oo", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert set(affected) == {"base-plate", "bracket"}

        # Each affected node would trigger vcad_update_cascade
        for node_id in affected:
            node = dag.get_node(node_id)
            assert node is not None

    def test_mixed_changes_flow(self, dag, tmp_path):
        """Mixed .skp.oo and .oo changes handled separately."""
        source_a = str(tmp_path / "base-plate.skp.oo")
        source_b = str(tmp_path / "bracket.skp.oo")

        dag.add_node(VCADNode(node_id="base-plate", source_file=source_a))
        dag.add_node(VCADNode(node_id="bracket", source_file=source_b))

        watcher = VCADFileWatcher()

        # Setup mock
        mock_vcad = MagicMock()
        mock_vcad.get_affected_nodes.return_value = ["bracket"]

        changes = [
            # Direct .skp.oo change
            {"path": source_a, "kind": "vcad_loon"},
            # Library .oo change
            {"path": "/project/src/helpers.oo", "kind": "loon"},
        ]

        # .skp.oo changes: find direct node matches
        skp_oo_nodes = watcher.find_nodes_for_changes(changes, dag)
        assert skp_oo_nodes == ["base-plate"]

        # .oo changes: find affected via module tracker
        loon_nodes = watcher.find_nodes_for_loon_changes(changes, mock_vcad)
        assert loon_nodes == ["bracket"]

        # Combined: all affected nodes (deduplicated)
        all_affected = set(skp_oo_nodes) | set(loon_nodes)
        assert all_affected == {"base-plate", "bracket"}

    def test_loon_change_no_affected_nodes(self, dag, tmp_path):
        """Loon change with no affected nodes produces no cascades."""
        source = str(tmp_path / "base-plate.skp.oo")
        dag.add_node(VCADNode(node_id="base-plate", source_file=source))

        watcher = VCADFileWatcher()

        mock_vcad = MagicMock()
        mock_vcad.get_affected_nodes.return_value = []

        changes = [
            {"path": "/project/src/unused.oo", "kind": "loon"},
        ]
        affected = watcher.find_nodes_for_loon_changes(changes, mock_vcad)

        assert affected == []
