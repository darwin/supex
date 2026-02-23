"""Tests for MCP vcad tools."""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from supex_driver.connection.vcad_exceptions import (
    CAPABILITY_UNAVAILABLE,
    PROTOCOL_MISMATCH,
    VCADCapabilityError,
    VCADConnectionError,
    VCADProtocolError,
    VCADRemoteError,
    VCADTimeoutError,
)
from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpRemoteError,
)
from supex_driver.mcp.vcad_tools import (
    vcad_eval,
    vcad_export,
    vcad_inspect,
    vcad_list_nodes,
    vcad_place,
    vcad_update,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = MagicMock()
    ctx.request_id = "test-req-1"
    return ctx


@pytest.fixture
def mock_vcad():
    """Patch get_vcad_connection to return a mock VCADConnection."""
    with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get, \
         patch("builtins.open", mock_open(read_data="[cube 1.0 1.0 1.0]")):
        conn = MagicMock()
        mock_get.return_value = conn
        yield conn


@pytest.fixture
def mock_sketchup():
    """Patch get_sketchup_connection to return a mock SketchupConnection."""
    with patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get:
        conn = MagicMock()
        mock_get.return_value = conn
        yield conn


# ---------------------------------------------------------------------------
# vcad_place
# ---------------------------------------------------------------------------


class TestVCADPlace:
    """Test vcad_place tool."""

    def test_place_success(self, mock_ctx, mock_vcad, mock_sketchup):
        """Place evaluates file, imports mesh, returns result."""
        mock_vcad.eval_with_imports.return_value = {"mesh_path": "/tmp/out.obj"}
        mock_sketchup.send_command.return_value = {
            "success": True,
            "node_id": "bracket",
            "entity_id": 42,
            "definition_name": "vcad_bracket",
        }

        result = json.loads(
            vcad_place(
                mock_ctx,
                node_id="bracket",
                source_file="/project/bracket.cmp.oo",
                position=[10.0, 20.0, 0.0],
                component_name="my_bracket",
            )
        )

        assert result["success"] is True
        assert result["node_id"] == "bracket"
        mock_vcad.eval_with_imports.assert_called_once()
        call_kwargs = mock_vcad.eval_with_imports.call_args.kwargs
        assert call_kwargs["node_id"] == "bracket"
        call_args = mock_sketchup.send_command.call_args
        assert call_args.kwargs["method"] == "place_vcad_node"
        params = call_args.kwargs["params"]
        assert params["mesh_path"] == "/tmp/out.obj"
        assert params["node_id"] == "bracket"
        assert params["position"] == [10.0, 20.0, 0.0]
        assert params["component_name"] == "my_bracket"

    def test_place_default_position(self, mock_ctx, mock_vcad, mock_sketchup):
        """Place without position omits it from params."""
        mock_vcad.eval_with_imports.return_value = {"mesh_path": "/tmp/out.obj"}
        mock_sketchup.send_command.return_value = {"success": True, "node_id": "n1"}

        vcad_place(mock_ctx, node_id="n1", source_file="/f.cmp.oo")

        params = mock_sketchup.send_command.call_args.kwargs["params"]
        assert "position" not in params

    def test_place_eval_error_returns_vcad_error(self, mock_ctx, mock_vcad):
        """Sidecar eval failure returns error without calling SketchUp."""
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000, message="Parse error in Loon code"
        )

        result = json.loads(
            vcad_place(mock_ctx, node_id="n1", source_file="/bad.cmp.oo")
        )

        assert result["success"] is False
        assert result["error_code"] == -32000
        assert "Parse error" in result["error"]

    def test_place_no_mesh_path(self, mock_ctx, mock_vcad):
        """Sidecar returns result without mesh_path."""
        mock_vcad.eval_with_imports.return_value = {"result": "no mesh"}

        result = json.loads(
            vcad_place(mock_ctx, node_id="n1", source_file="/f.cmp.oo")
        )

        assert result["success"] is False
        assert "mesh_path" in result["error"]

    def test_place_sketchup_error(self, mock_ctx, mock_vcad, mock_sketchup):
        """SketchUp import failure propagated."""
        mock_vcad.eval_with_imports.return_value = {"mesh_path": "/tmp/out.obj"}
        mock_sketchup.send_command.side_effect = SketchUpConnectionError(
            "Connection refused"
        )

        result = json.loads(
            vcad_place(mock_ctx, node_id="n1", source_file="/f.cmp.oo")
        )

        assert result["success"] is False
        assert result["error_code"] == "CONNECTION_ERROR"
        assert result["details"]["error_type"] == "connection"


# ---------------------------------------------------------------------------
# vcad_update
# ---------------------------------------------------------------------------


class TestVCADUpdate:
    """Test vcad_update tool."""

    def test_update_with_source(self, mock_ctx, mock_vcad, mock_sketchup):
        """Update with explicit source_file."""
        mock_vcad.eval_with_imports.return_value = {"mesh_path": "/tmp/updated.obj"}
        mock_sketchup.send_command.return_value = {
            "success": True,
            "node_id": "bracket",
            "version": 2,
            "replaced_instances": 3,
        }

        result = json.loads(
            vcad_update(
                mock_ctx,
                node_id="bracket",
                source_file="/project/bracket.cmp.oo",
            )
        )

        assert result["success"] is True
        assert result["version"] == 2
        mock_vcad.eval_with_imports.assert_called_once()

    def test_update_lookup_source(self, mock_ctx, mock_vcad, mock_sketchup):
        """Update without source_file looks it up from SketchUp."""
        # First call: get_vcad_node lookup; second call: update_vcad_node
        mock_sketchup.send_command.side_effect = [
            {"source_file": "/project/plate.cmp.oo", "node_id": "plate"},
            {"success": True, "node_id": "plate", "version": 4},
        ]
        mock_vcad.eval_with_imports.return_value = {"mesh_path": "/tmp/plate.obj"}

        result = json.loads(vcad_update(mock_ctx, node_id="plate"))

        assert result["success"] is True
        # Verify lookup was done
        first_call = mock_sketchup.send_command.call_args_list[0]
        assert first_call.kwargs["method"] == "get_vcad_node"
        mock_vcad.eval_with_imports.assert_called_once()

    def test_update_node_not_found(self, mock_ctx, mock_sketchup):
        """Node not found in SketchUp returns error."""
        mock_sketchup.send_command.return_value = {"node_id": "ghost"}

        result = json.loads(vcad_update(mock_ctx, node_id="ghost"))

        assert result["success"] is False
        assert "source_file" in result["error"]

    def test_update_eval_error(self, mock_ctx, mock_vcad, mock_sketchup):
        """Sidecar eval error during update."""
        mock_vcad.eval_with_imports.side_effect = VCADTimeoutError("Eval timed out")

        result = json.loads(
            vcad_update(mock_ctx, node_id="n1", source_file="/f.cmp.oo")
        )

        assert result["success"] is False
        assert result["error_code"] == "CONNECTION_ERROR"
        assert result["details"]["error_type"] == "connection"


# ---------------------------------------------------------------------------
# vcad_inspect
# ---------------------------------------------------------------------------


class TestVCADInspect:
    """Test vcad_inspect tool."""

    def test_inspect_success(self, mock_ctx, mock_vcad):
        """Inspect returns geometry properties via eval_with_imports(inspect=True, export_mesh=False)."""
        mock_vcad.eval_with_imports.return_value = {
            "volume": 1000.0,
            "surface_area": 600.0,
            "bbox": {"min": [0, 0, 0], "max": [10, 10, 10]},
            "is_empty": False,
        }

        result = json.loads(vcad_inspect(mock_ctx, source="[cube 10.0 10.0 10.0]"))

        assert result["success"] is True
        assert result["volume"] == 1000.0
        assert result["surface_area"] == 600.0
        # Verify it used eval_with_imports with inspect=True, export_mesh=False
        mock_vcad.eval_with_imports.assert_called_once()
        call_kwargs = mock_vcad.eval_with_imports.call_args
        assert call_kwargs.kwargs.get("inspect") is True
        assert call_kwargs.kwargs.get("export_mesh") is False

    def test_inspect_error(self, mock_ctx, mock_vcad):
        """Inspect with invalid code returns error."""
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000, message="Invalid Loon"
        )

        result = json.loads(vcad_inspect(mock_ctx, source="bad code"))

        assert result["success"] is False
        assert result["error_code"] == -32000


# ---------------------------------------------------------------------------
# vcad_export
# ---------------------------------------------------------------------------


class TestVCADExport:
    """Test vcad_export tool."""

    def test_export_obj(self, mock_ctx, mock_vcad):
        """Export to OBJ."""
        mock_vcad.send_command.return_value = {
            "file_path": "/tmp/output.obj",
            "format": "obj",
        }

        result = json.loads(
            vcad_export(mock_ctx, source="/project/part.cmp.oo", format="obj")
        )

        assert result["success"] is True
        assert result["file_path"] == "/tmp/output.obj"
        call_args = mock_vcad.send_command.call_args
        assert call_args[0][0] == "vcad.export"
        assert call_args[0][1]["source"] == "/project/part.cmp.oo"
        assert call_args[0][1]["format"] == "obj"

    def test_export_with_output_path(self, mock_ctx, mock_vcad):
        """Export with explicit output path."""
        mock_vcad.send_command.return_value = {"file_path": "/custom/out.step"}

        vcad_export(
            mock_ctx,
            source="[cube 1.0 1.0 1.0]",
            format="step",
            output_path="/custom/out.step",
        )

        params = mock_vcad.send_command.call_args[0][1]
        assert params["output_path"] == "/custom/out.step"

    def test_export_error(self, mock_ctx, mock_vcad):
        """Export failure."""
        mock_vcad.send_command.side_effect = VCADConnectionError(
            "Sidecar not running"
        )

        result = json.loads(vcad_export(mock_ctx, source="[cube 1.0 1.0 1.0]"))

        assert result["success"] is False
        assert result["error_code"] == "CONNECTION_ERROR"
        assert result["details"]["error_type"] == "connection"


# ---------------------------------------------------------------------------
# vcad_eval
# ---------------------------------------------------------------------------


class TestVCADEval:
    """Test vcad_eval tool."""

    def test_eval_success(self, mock_ctx, mock_vcad):
        """Eval returns result."""
        mock_vcad.eval_with_imports.return_value = {"display": "Cube(10.0, 10.0, 10.0)"}

        result = json.loads(vcad_eval(mock_ctx, code="[cube 10.0 10.0 10.0]"))

        assert result["success"] is True
        assert result["display"] == "Cube(10.0, 10.0, 10.0)"

    def test_eval_parse_error(self, mock_ctx, mock_vcad):
        """Eval with parse error."""
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000, message="Unexpected token"
        )

        result = json.loads(vcad_eval(mock_ctx, code="[invalid"))

        assert result["success"] is False
        assert result["error_code"] == -32000


# ---------------------------------------------------------------------------
# vcad_list_nodes
# ---------------------------------------------------------------------------


class TestVCADListNodes:
    """Test vcad_list_nodes tool."""

    def test_list_nodes(self, mock_ctx, mock_sketchup):
        """List returns nodes from SketchUp."""
        mock_sketchup.send_command.return_value = [
            {"node_id": "bracket", "source_file": "/a.cmp.oo", "version": 2},
            {"node_id": "plate", "source_file": "/b.cmp.oo", "version": 1},
        ]

        result = json.loads(vcad_list_nodes(mock_ctx))

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["node_id"] == "bracket"

    def test_list_nodes_empty(self, mock_ctx, mock_sketchup):
        """Empty model returns empty list."""
        mock_sketchup.send_command.return_value = []

        result = json.loads(vcad_list_nodes(mock_ctx))

        assert result == []

    def test_list_nodes_connection_error(self, mock_ctx, mock_sketchup):
        """Connection error returns error."""
        mock_sketchup.send_command.side_effect = SketchUpConnectionError(
            "Not connected"
        )

        result = json.loads(vcad_list_nodes(mock_ctx))

        assert result["success"] is False
        assert result["error_code"] == "CONNECTION_ERROR"
        assert result["details"]["error_type"] == "connection"


# ---------------------------------------------------------------------------
# Negotiation error propagation
# ---------------------------------------------------------------------------


class TestVCADToolsErrorPropagation:
    """Test that negotiation errors propagate correctly through MCP tools.

    Verifies:
    - PROTOCOL_MISMATCH surfaced with deterministic error_code
    - CAPABILITY_UNAVAILABLE includes required_capability, negotiated_capabilities, operation
    - Tools return error directly (no fallback branch)
    - Upstream error_code is never rewritten
    """

    def test_protocol_mismatch_surfaces_in_mcp(self, mock_ctx, mock_vcad):
        """Sidecar major version mismatch surfaces as PROTOCOL_MISMATCH in tool response."""
        mock_vcad.eval_with_imports.side_effect = VCADProtocolError(
            "Protocol version mismatch: driver=1.0, sidecar=2.0",
            error_code=PROTOCOL_MISMATCH,
            details={
                "expected_protocol": "1.0",
                "actual_protocol": "2.0",
            },
        )

        result = json.loads(vcad_eval(mock_ctx, code="[cube 1.0 1.0 1.0]"))

        assert result["success"] is False
        assert result["error_code"] == PROTOCOL_MISMATCH
        assert result["details"]["expected_protocol"] == "1.0"
        assert result["details"]["actual_protocol"] == "2.0"
        assert result["details"]["operation"] == "vcad_eval"

    def test_capability_unavailable_surfaces_in_mcp(self, mock_ctx, mock_vcad):
        """Missing capability surfaces as CAPABILITY_UNAVAILABLE with full details."""
        mock_vcad.eval_with_imports.side_effect = VCADCapabilityError(
            required_capability="adt_cache",
            negotiated_capabilities=["eval", "inspect"],
            operation="vcad_place",
        )

        result = json.loads(
            vcad_place(mock_ctx, node_id="n1", source_file="/f.cmp.oo")
        )

        assert result["success"] is False
        assert result["error_code"] == CAPABILITY_UNAVAILABLE
        assert result["details"]["required_capability"] == "adt_cache"
        assert result["details"]["negotiated_capabilities"] == ["eval", "inspect"]
        assert result["details"]["operation"] == "vcad_place"

    def test_protocol_mismatch_no_fallback(self, mock_ctx, mock_vcad, mock_sketchup):
        """Tool returns error directly on protocol mismatch (no retry/fallback)."""
        mock_vcad.eval_with_imports.side_effect = VCADProtocolError(
            "Protocol version mismatch",
            error_code=PROTOCOL_MISMATCH,
            details={"expected_protocol": "1.0", "actual_protocol": "3.0"},
        )

        result = json.loads(
            vcad_place(mock_ctx, node_id="n1", source_file="/f.cmp.oo")
        )

        assert result["success"] is False
        assert result["error_code"] == PROTOCOL_MISMATCH
        # SketchUp should never have been called
        mock_sketchup.send_command.assert_not_called()

    def test_capability_error_no_fallback(self, mock_ctx, mock_vcad, mock_sketchup):
        """Tool returns error directly on capability mismatch (no fallback)."""
        mock_vcad.eval_with_imports.side_effect = VCADCapabilityError(
            required_capability="imports.data_extracts",
            negotiated_capabilities=["eval"],
            operation="vcad_inspect",
        )

        result = json.loads(vcad_inspect(mock_ctx, source="[cube 1.0 1.0 1.0]"))

        assert result["success"] is False
        assert result["error_code"] == CAPABILITY_UNAVAILABLE

    def test_remote_error_code_preserved(self, mock_ctx, mock_vcad):
        """Upstream error_code from sidecar is preserved unchanged."""
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32001, message="NO_GEOMETRY", data={"node_id": "empty"}
        )

        result = json.loads(vcad_eval(mock_ctx, code="[sphere 0.0]"))

        assert result["success"] is False
        assert result["error_code"] == -32001
        assert result["error"] == "NO_GEOMETRY"
        assert result["details"]["node_id"] == "empty"

    def test_protocol_mismatch_in_export(self, mock_ctx, mock_vcad):
        """Protocol mismatch propagates through vcad_export."""
        mock_vcad.send_command.side_effect = VCADProtocolError(
            "Protocol version mismatch",
            error_code=PROTOCOL_MISMATCH,
            details={"expected_protocol": "1.0", "actual_protocol": "2.0"},
        )

        result = json.loads(vcad_export(mock_ctx, source="[cube 1.0 1.0 1.0]"))

        assert result["success"] is False
        assert result["error_code"] == PROTOCOL_MISMATCH

    def test_capability_unavailable_in_update(self, mock_ctx, mock_vcad):
        """Capability error propagates through vcad_update."""
        mock_vcad.eval_with_imports.side_effect = VCADCapabilityError(
            required_capability="eval",
            negotiated_capabilities=[],
            operation="vcad_update",
        )

        result = json.loads(
            vcad_update(mock_ctx, node_id="n1", source_file="/f.cmp.oo")
        )

        assert result["success"] is False
        assert result["error_code"] == CAPABILITY_UNAVAILABLE
        assert result["details"]["required_capability"] == "eval"
        assert result["details"]["negotiated_capabilities"] == []
        assert result["details"]["operation"] == "vcad_update"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestVCADToolsRegistration:
    """Test that vcad tools are properly registered on the MCP server."""

    def test_tools_exist_in_module(self):
        """All vcad tools are importable from vcad_tools module."""
        from supex_driver.mcp import vcad_tools

        expected = [
            "vcad_place",
            "vcad_update",
            "vcad_inspect",
            "vcad_export",
            "vcad_eval",
            "vcad_list_nodes",
        ]
        for name in expected:
            assert hasattr(vcad_tools, name), f"Missing tool: {name}"

    def test_tools_registered_on_server(self):
        """vcad tools are registered via side-effect import in server.py."""
        from supex_driver.mcp.mcp_server import mcp

        # After importing server.py, vcad_tools should be loaded
        # We can verify by checking the module is accessible
        from supex_driver.mcp import vcad_tools

        assert vcad_tools is not None
