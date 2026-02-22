"""Tests for VCAD data import extraction and MCP tool (vcad_place_with_imports).

Unit tests using mocked sidecar and SketchUp connections.
"""

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpRemoteError,
)
from supex_driver.connection.vcad_exceptions import (
    VCADConnectionError,
    VCADRemoteError,
)
from supex_driver.mcp.vcad_tools import vcad_place_with_imports


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = MagicMock()
    ctx.request_id = "test-req-import-1"
    return ctx


@pytest.fixture
def mock_vcad():
    """Patch get_vcad_connection to return a mock VCADConnection."""
    with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get:
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


@pytest.fixture
def source_file(tmp_path):
    """Create a temporary .skp.oo source file with imports."""
    src = tmp_path / "part.skp.oo"
    src.write_text(
        '[let host-dims [import :dimensions "entity:12345"]]\n'
        "[pipe [cube [get host-dims :width] 10.0 [get host-dims :height]]\n"
        "  [fillet 2.0]]"
    )
    return str(src)


@pytest.fixture
def source_file_no_imports(tmp_path):
    """Create a source file without imports."""
    src = tmp_path / "simple.skp.oo"
    src.write_text("[cube 10.0 10.0 10.0]")
    return str(src)


# ---------------------------------------------------------------------------
# vcad_place_with_imports — success paths
# ---------------------------------------------------------------------------


class TestVCADPlaceWithImports:
    """Test vcad_place_with_imports MCP tool."""

    def test_place_with_imports_success(
        self, mock_ctx, mock_vcad, mock_sketchup, source_file
    ):
        """Full flow: extract imports, resolve, eval, place."""
        # Sidecar extract_imports
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "host-dims",
                    "extract": "dimensions",
                    "entity_ref": "entity:12345",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let host-dims __vcad_import_0]\n[cube 10.0 10.0 10.0]",
        }

        # SketchUp resolve_vcad_import
        mock_sketchup.send_command.side_effect = [
            {
                "extract": "dimensions",
                "vcad_node_id": None,
                "data": {"width": 100.0, "height": 200.0, "depth": 50.0},
            },
            {
                "success": True,
                "node_id": "my-part",
                "entity_id": 99,
                "definition_name": "vcad_my-part",
            },
        ]

        # Sidecar eval_with_imports
        mock_vcad.eval_with_imports.return_value = {
            "obj_path": "/tmp/import-eval-001.dae",
            "volume": 1000.0,
            "surface_area": 600.0,
        }

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="my-part",
                source_file=source_file,
                position=[0.0, 0.0, 0.0],
            )
        )

        assert result["success"] is True
        assert result["node_id"] == "my-part"

        # Verify extract_imports was called with source content
        mock_vcad.extract_imports.assert_called_once()
        call_args = mock_vcad.extract_imports.call_args
        assert "import" in call_args[0][0]

        # Verify resolve_vcad_import was called
        resolve_call = mock_sketchup.send_command.call_args_list[0]
        assert resolve_call.kwargs["method"] == "resolve_vcad_import"
        assert resolve_call.kwargs["params"]["entity_id"] == "12345"
        assert resolve_call.kwargs["params"]["extract"] == "dimensions"

        # Verify eval_with_imports was called with resolved data
        mock_vcad.eval_with_imports.assert_called_once()
        eval_call = mock_vcad.eval_with_imports.call_args
        assert eval_call.kwargs["imports"]["import_0"]["data"]["width"] == 100.0

    def test_place_no_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, source_file_no_imports
    ):
        """Source without imports: no resolve step, eval_with_imports with empty imports."""
        mock_vcad.extract_imports.return_value = {
            "imports": [],
            "transformed_source": "[cube 10.0 10.0 10.0]",
        }
        mock_vcad.eval_with_imports.return_value = {
            "obj_path": "/tmp/eval-001.dae",
        }
        mock_sketchup.send_command.return_value = {
            "success": True,
            "node_id": "simple",
            "entity_id": 50,
        }

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="simple",
                source_file=source_file_no_imports,
            )
        )

        assert result["success"] is True
        # No resolve_vcad_import call — only place_vcad_node
        assert mock_sketchup.send_command.call_count == 1
        assert mock_sketchup.send_command.call_args.kwargs["method"] == "place_vcad_node"

    def test_place_multiple_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Multiple imports resolved in order."""
        src = tmp_path / "multi.skp.oo"
        src.write_text(
            '[let dims [import :dimensions "entity:100"]]\n'
            '[let bb [import :bbox "entity:200"]]\n'
            "[cube 1.0 1.0 1.0]"
        )

        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "dims",
                    "extract": "dimensions",
                    "entity_ref": "entity:100",
                    "injected_symbol": "__vcad_import_0",
                },
                {
                    "import_id": "import_1",
                    "binding_name": "bb",
                    "extract": "bbox",
                    "entity_ref": "entity:200",
                    "injected_symbol": "__vcad_import_1",
                },
            ],
            "transformed_source": "[let dims __vcad_import_0]\n[let bb __vcad_import_1]\n[cube 1.0 1.0 1.0]",
        }
        mock_sketchup.send_command.side_effect = [
            {
                "extract": "dimensions",
                "vcad_node_id": "plate",
                "data": {"width": 50.0, "height": 30.0, "depth": 10.0},
            },
            {
                "extract": "bbox",
                "vcad_node_id": None,
                "data": {"min": [0.0, 0.0, 0.0], "max": [50.0, 30.0, 10.0]},
            },
            {
                "success": True,
                "node_id": "multi",
                "entity_id": 77,
            },
        ]
        mock_vcad.eval_with_imports.return_value = {
            "obj_path": "/tmp/multi.dae",
        }

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="multi", source_file=str(src)
            )
        )

        assert result["success"] is True
        # Two resolve calls + one place call
        assert mock_sketchup.send_command.call_count == 3


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestVCADPlaceWithImportsErrors:
    """Test error handling in vcad_place_with_imports."""

    def test_source_file_not_found(self, mock_ctx):
        """Missing source file returns IO error."""
        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="n1",
                source_file="/nonexistent/file.skp.oo",
            )
        )
        assert result["success"] is False
        assert result["error_type"] == "io"

    def test_extract_imports_error(self, mock_ctx, mock_vcad, source_file):
        """Sidecar extract_imports failure propagated."""
        mock_vcad.extract_imports.side_effect = VCADRemoteError(
            code=-32000,
            message="IMPORT_FORM_INVALID: bad import syntax",
            data={"error_code": "IMPORT_FORM_INVALID"},
        )

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="n1", source_file=source_file
            )
        )
        assert result["success"] is False
        assert result["error_code"] == -32000

    def test_resolve_import_error(
        self, mock_ctx, mock_vcad, mock_sketchup, source_file
    ):
        """SketchUp resolve failure propagated."""
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "x",
                    "extract": "dimensions",
                    "entity_ref": "entity:999",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let x __vcad_import_0]",
        }
        mock_sketchup.send_command.side_effect = SketchUpRemoteError(
            code=-32603, message="Entity not found: 999"
        )

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="n1", source_file=source_file
            )
        )
        assert result["success"] is False
        assert result["error_type"] == "remote"

    def test_eval_with_imports_error(
        self, mock_ctx, mock_vcad, mock_sketchup, source_file
    ):
        """Sidecar eval_with_imports failure propagated."""
        mock_vcad.extract_imports.return_value = {
            "imports": [],
            "transformed_source": "[cube 1.0 1.0 1.0]",
        }
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000, message="LOON_ERROR: undefined binding"
        )

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="n1", source_file=source_file
            )
        )
        assert result["success"] is False
        assert result["error_code"] == -32000

    def test_no_obj_path_in_eval_result(
        self, mock_ctx, mock_vcad, mock_sketchup, source_file
    ):
        """Sidecar eval returns no obj_path."""
        mock_vcad.extract_imports.return_value = {
            "imports": [],
            "transformed_source": "[cube 1.0 1.0 1.0]",
        }
        mock_vcad.eval_with_imports.return_value = {"volume": 100.0}

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="n1", source_file=source_file
            )
        )
        assert result["success"] is False
        assert "obj_path" in result["error"]

    def test_sketchup_place_error(
        self, mock_ctx, mock_vcad, mock_sketchup, source_file
    ):
        """SketchUp place failure after successful eval."""
        mock_vcad.extract_imports.return_value = {
            "imports": [],
            "transformed_source": "[cube 1.0 1.0 1.0]",
        }
        mock_vcad.eval_with_imports.return_value = {
            "obj_path": "/tmp/out.dae",
        }
        mock_sketchup.send_command.side_effect = SketchUpConnectionError(
            "Connection refused"
        )

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="n1", source_file=source_file
            )
        )
        assert result["success"] is False
        assert result["error_type"] == "connection"

    def test_vcad_connection_error_during_extract(
        self, mock_ctx, mock_vcad, source_file
    ):
        """VCAD connection error during extract propagated."""
        mock_vcad.extract_imports.side_effect = VCADConnectionError(
            "Sidecar not running"
        )

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx, node_id="n1", source_file=source_file
            )
        )
        assert result["success"] is False
        assert result["error_type"] == "connection"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestVCADDataImportsRegistration:
    """Test that vcad_place_with_imports is properly registered."""

    def test_tool_exists_in_module(self):
        """vcad_place_with_imports is importable."""
        from supex_driver.mcp import vcad_tools

        assert hasattr(vcad_tools, "vcad_place_with_imports")

    def test_tool_callable(self):
        """vcad_place_with_imports is a callable."""
        assert callable(vcad_place_with_imports)
