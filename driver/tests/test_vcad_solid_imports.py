"""Tests for VCAD solid (ADT) import system.

Tests the :solid import flow where cached ADT values from vcad-backed
entities are injected into the Loon environment for cross-node CSG composition.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from supex_driver.connection.sketchup_exceptions import (
    SketchUpRemoteError,
)
from supex_driver.connection.vcad_exceptions import (
    VCADRemoteError,
)
from supex_driver.mcp.vcad_tools import (
    _build_import_refs,
    vcad_place,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = MagicMock()
    ctx.request_id = "test-req-solid-1"
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
def solid_source_file(tmp_path):
    """Create a .skp.oo source file with a :solid import."""
    src = tmp_path / "consumer.skp.oo"
    src.write_text(
        '[let bracket [import :solid "entity:67890"]]\n'
        "[pipe [cube 20.0 20.0 50.0]\n"
        "  [difference bracket]\n"
        "  [translate 0.0 0.0 10.0]]"
    )
    return str(src)


@pytest.fixture
def mixed_source_file(tmp_path):
    """Create a source file with both data and solid imports."""
    src = tmp_path / "mixed.skp.oo"
    src.write_text(
        '[let dims [import :dimensions "entity:100"]]\n'
        '[let bracket [import :solid "entity:200"]]\n'
        "[pipe [cube [get dims :width] 10.0 [get dims :height]]\n"
        "  [difference bracket]]"
    )
    return str(src)


# ---------------------------------------------------------------------------
# Solid import — success paths
# ---------------------------------------------------------------------------


class TestSolidImportSuccess:
    """Test solid import flow through vcad_place."""

    def test_solid_import_uses_eval_with_solid_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, solid_source_file
    ):
        """Solid import triggers eval_with_solid_imports sidecar path."""
        # Sidecar extract_imports
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "bracket",
                    "extract": "solid",
                    "entity_ref": "entity:67890",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let bracket __vcad_import_0]\n[cube 10.0 10.0 10.0]",
        }

        # SketchUp resolve_vcad_import returns vcad-backed entity
        mock_sketchup.send_command.side_effect = [
            {
                "extract": "solid",
                "source": "vcad",
                "vcad_node_id": "bracket-node",
            },
            {
                "success": True,
                "node_id": "consumer",
                "entity_id": 101,
                "definition_name": "vcad_consumer",
            },
        ]

        # Sidecar eval_with_solid_imports
        mock_vcad.eval_with_solid_imports.return_value = {
            "obj_path": "/tmp/import-eval-001.dae",
            "volume": 500.0,
            "surface_area": 300.0,
        }

        result = json.loads(
            vcad_place(
                mock_ctx,
                node_id="consumer",
                source_file=solid_source_file,
            )
        )

        assert result["success"] is True
        assert result["node_id"] == "consumer"

        # Verify eval_with_solid_imports was called (not eval_with_imports)
        mock_vcad.eval_with_solid_imports.assert_called_once()
        mock_vcad.eval_with_imports.assert_not_called()

        # Verify the imports dict contains vcad_node_id
        call_kwargs = mock_vcad.eval_with_solid_imports.call_args.kwargs
        import_0 = call_kwargs["imports"]["import_0"]
        assert import_0["extract"] == "solid"
        assert import_0["vcad_node_id"] == "bracket-node"
        assert import_0["data"] is None

        # Verify node_id is passed for caching
        assert call_kwargs["node_id"] == "consumer"

    def test_mixed_data_and_solid_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, mixed_source_file
    ):
        """Mixed data + solid imports use eval_with_solid_imports path."""
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
                    "binding_name": "bracket",
                    "extract": "solid",
                    "entity_ref": "entity:200",
                    "injected_symbol": "__vcad_import_1",
                },
            ],
            "transformed_source": "[let dims __vcad_import_0]\n[let bracket __vcad_import_1]\n[cube 1.0 1.0 1.0]",
        }

        # Two resolve calls: first for data, second for solid
        mock_sketchup.send_command.side_effect = [
            {
                "extract": "dimensions",
                "vcad_node_id": None,
                "data": {"width": 100.0, "height": 200.0, "depth": 50.0},
            },
            {
                "extract": "solid",
                "source": "vcad",
                "vcad_node_id": "bracket-node",
            },
            {
                "success": True,
                "node_id": "mixed",
                "entity_id": 102,
            },
        ]

        mock_vcad.eval_with_solid_imports.return_value = {
            "obj_path": "/tmp/mixed.dae",
            "volume": 800.0,
        }

        result = json.loads(
            vcad_place(
                mock_ctx,
                node_id="mixed",
                source_file=mixed_source_file,
            )
        )

        assert result["success"] is True

        # eval_with_solid_imports used (has solid imports)
        mock_vcad.eval_with_solid_imports.assert_called_once()
        mock_vcad.eval_with_imports.assert_not_called()

        # Both imports present in the call
        call_kwargs = mock_vcad.eval_with_solid_imports.call_args.kwargs
        imports = call_kwargs["imports"]
        assert imports["import_0"]["extract"] == "dimensions"
        assert imports["import_0"]["data"]["width"] == 100.0
        assert imports["import_1"]["extract"] == "solid"
        assert imports["import_1"]["vcad_node_id"] == "bracket-node"

    def test_data_only_imports_use_eval_with_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Data-only imports use the original eval_with_imports path."""
        src = tmp_path / "data-only.skp.oo"
        src.write_text(
            '[let dims [import :dimensions "entity:100"]]\n'
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
            ],
            "transformed_source": "[let dims __vcad_import_0]\n[cube 1.0 1.0 1.0]",
        }

        mock_sketchup.send_command.side_effect = [
            {
                "extract": "dimensions",
                "vcad_node_id": None,
                "data": {"width": 100.0, "height": 200.0, "depth": 50.0},
            },
            {
                "success": True,
                "node_id": "data-only",
                "entity_id": 50,
            },
        ]

        mock_vcad.eval_with_imports.return_value = {
            "obj_path": "/tmp/data-only.dae",
        }

        result = json.loads(
            vcad_place(
                mock_ctx,
                node_id="data-only",
                source_file=str(src),
            )
        )

        assert result["success"] is True
        # eval_with_imports used (no solid imports)
        mock_vcad.eval_with_imports.assert_called_once()
        mock_vcad.eval_with_solid_imports.assert_not_called()


# ---------------------------------------------------------------------------
# Solid import — error paths
# ---------------------------------------------------------------------------


class TestSolidImportErrors:
    """Test error handling for solid imports."""

    def test_solid_import_non_vcad_entity_error(
        self, mock_ctx, mock_vcad, mock_sketchup, solid_source_file
    ):
        """Non-vcad entity requesting :solid returns error from SketchUp."""
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "bracket",
                    "extract": "solid",
                    "entity_ref": "entity:999",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let bracket __vcad_import_0]",
        }

        # SketchUp raises error for non-vcad entity
        mock_sketchup.send_command.side_effect = SketchUpRemoteError(
            code=-32603,
            message="Entity 999 is not vcad-backed — :solid import unavailable",
        )

        result = json.loads(
            vcad_place(
                mock_ctx,
                node_id="bad-solid",
                source_file=solid_source_file,
            )
        )

        assert result["success"] is False
        assert result["error_code"] == -32603
        assert result["details"]["error_type"] == "remote"

    def test_solid_import_adt_cache_miss(
        self, mock_ctx, mock_vcad, mock_sketchup, solid_source_file
    ):
        """ADT cache miss from sidecar is propagated as error."""
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "bracket",
                    "extract": "solid",
                    "entity_ref": "entity:67890",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let bracket __vcad_import_0]\n[cube 1.0 1.0 1.0]",
        }

        mock_sketchup.send_command.return_value = {
            "extract": "solid",
            "source": "vcad",
            "vcad_node_id": "missing-node",
        }

        # Sidecar returns cache miss error
        mock_vcad.eval_with_solid_imports.side_effect = VCADRemoteError(
            code=-32000,
            message="ADT_CACHE_MISS: no cached ADT for node 'missing-node'",
            data={"error_code": "LOON_ERROR"},
        )

        result = json.loads(
            vcad_place(
                mock_ctx,
                node_id="consumer",
                source_file=solid_source_file,
            )
        )

        assert result["success"] is False
        assert result["error_code"] == -32000


# ---------------------------------------------------------------------------
# DAG import ref building with solid imports
# ---------------------------------------------------------------------------


class TestBuildImportRefsWithSolid:
    """Test _build_import_refs handles solid imports correctly."""

    def test_solid_import_creates_vcad_type_ref(self):
        """Solid import resolved_type is 'vcad' with source_node_id."""
        import_decls = [
            {
                "import_id": "import_0",
                "binding_name": "bracket",
                "extract": "solid",
                "entity_ref": "entity:200",
                "injected_symbol": "__vcad_import_0",
            }
        ]
        resolved_imports = {
            "import_0": {
                "extract": "solid",
                "injected_symbol": "__vcad_import_0",
                "data": None,
                "vcad_node_id": "bracket-node",
            }
        }

        refs = _build_import_refs(import_decls, resolved_imports)

        assert len(refs) == 1
        assert refs[0].extract == "solid"
        assert refs[0].resolved_type == "vcad"
        assert refs[0].source_node_id == "bracket-node"

    def test_mixed_imports_ref_types(self):
        """Mixed data + solid imports produce correct ref types."""
        import_decls = [
            {
                "import_id": "import_0",
                "binding_name": "dims",
                "extract": "dimensions",
                "entity_ref": "entity:100",
                "injected_symbol": "__vcad_import_0",
            },
            {
                "import_id": "import_1",
                "binding_name": "bracket",
                "extract": "solid",
                "entity_ref": "entity:200",
                "injected_symbol": "__vcad_import_1",
            },
        ]
        resolved_imports = {
            "import_0": {
                "extract": "dimensions",
                "injected_symbol": "__vcad_import_0",
                "data": {"width": 100.0},
            },
            "import_1": {
                "extract": "solid",
                "injected_symbol": "__vcad_import_1",
                "data": None,
                "vcad_node_id": "bracket-node",
            },
        }

        refs = _build_import_refs(import_decls, resolved_imports)

        assert len(refs) == 2
        assert refs[0].extract == "dimensions"
        assert refs[0].resolved_type == "native"
        assert refs[0].source_node_id is None
        assert refs[1].extract == "solid"
        assert refs[1].resolved_type == "vcad"
        assert refs[1].source_node_id == "bracket-node"


# ---------------------------------------------------------------------------
# VCADConnection convenience method
# ---------------------------------------------------------------------------


class TestVCADConnectionSolidImports:
    """Test VCADConnection.eval_with_solid_imports method."""

    def test_eval_with_solid_imports_exists(self):
        """eval_with_solid_imports is a callable method on VCADConnection."""
        from supex_driver.connection.vcad_connection import VCADConnection

        assert hasattr(VCADConnection, "eval_with_solid_imports")
        assert callable(getattr(VCADConnection, "eval_with_solid_imports"))

    def test_eval_with_solid_imports_params(self):
        """eval_with_solid_imports builds correct params."""
        from supex_driver.connection.vcad_connection import VCADConnection

        conn = VCADConnection.__new__(VCADConnection)
        conn.send_command = MagicMock(return_value={"obj_path": "/tmp/out.dae"})

        conn.eval_with_solid_imports(
            transformed_source="[cube 10.0 10.0 10.0]",
            base_dir="/tmp/project",
            imports={"import_0": {"extract": "solid", "vcad_node_id": "node-a"}},
            node_id="node-b",
        )

        call_args = conn.send_command.call_args
        assert call_args[0][0] == "vcad.eval_with_solid_imports"
        params = call_args[0][1]
        assert params["transformed_source"] == "[cube 10.0 10.0 10.0]"
        assert params["base_dir"] == "/tmp/project"
        assert params["node_id"] == "node-b"
        assert "import_0" in params["imports"]
