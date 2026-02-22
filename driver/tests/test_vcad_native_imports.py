"""Tests for native SketchUp solid import (native mesh -> ImportedMesh ADT).

Tests the :solid import flow where native SketchUp solids (manifold geometry)
are extracted as mesh data and forwarded to the sidecar as ImportedMesh ADT.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from supex_driver.connection.sketchup_exceptions import (
    SketchUpRemoteError,
)
from supex_driver.mcp.vcad_tools import (
    _build_import_refs,
    vcad_place_with_imports,
)


# ---------------------------------------------------------------------------
# Sample mesh data (a simple tetrahedron)
# ---------------------------------------------------------------------------

SAMPLE_MESH = {
    "positions": [
        0.0, 0.0, 0.0,
        100.0, 0.0, 0.0,
        50.0, 86.6, 0.0,
        50.0, 28.87, 81.65,
    ],
    "indices": [0, 1, 2, 0, 1, 3, 1, 2, 3, 0, 2, 3],
    "normals": [
        0.0, 0.0, -1.0,
        0.0, 0.0, -1.0,
        0.0, 0.0, -1.0,
        0.0, 0.0, 1.0,
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = MagicMock()
    ctx.request_id = "test-req-native-1"
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
def native_solid_source(tmp_path):
    """Create a .skp.oo source file importing a native SketchUp solid."""
    src = tmp_path / "cut-from-native.skp.oo"
    src.write_text(
        '[let wall [import :solid "entity:11111"]]\n'
        "[pipe [cube 200.0 100.0 300.0]\n"
        "  [difference wall]]"
    )
    return str(src)


@pytest.fixture
def mixed_native_vcad_source(tmp_path):
    """Source with both native mesh and vcad-backed solid imports."""
    src = tmp_path / "mixed-native-vcad.skp.oo"
    src.write_text(
        '[let wall [import :solid "entity:11111"]]\n'
        '[let bracket [import :solid "entity:22222"]]\n'
        "[pipe [cube 200.0 100.0 300.0]\n"
        "  [difference wall]\n"
        "  [union bracket]]"
    )
    return str(src)


# ---------------------------------------------------------------------------
# Native mesh import — success paths
# ---------------------------------------------------------------------------


class TestNativeMeshImportSuccess:
    """Test native mesh import flow through vcad_place_with_imports."""

    def test_native_mesh_import_forwards_mesh_to_sidecar(
        self, mock_ctx, mock_vcad, mock_sketchup, native_solid_source
    ):
        """Native mesh import passes mesh data to eval_with_solid_imports."""
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "wall",
                    "extract": "solid",
                    "entity_ref": "entity:11111",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let wall __vcad_import_0]\n[cube 10.0 10.0 10.0]",
        }

        # SketchUp resolves as native mesh (manifold entity, not vcad-backed)
        mock_sketchup.send_command.side_effect = [
            {
                "extract": "solid",
                "source": "native_mesh",
                "mesh": SAMPLE_MESH,
            },
            {
                "success": True,
                "node_id": "consumer",
                "entity_id": 501,
                "definition_name": "vcad_consumer",
            },
        ]

        mock_vcad.eval_with_solid_imports.return_value = {
            "obj_path": "/tmp/native-mesh-001.dae",
            "volume": 6000000.0,
        }

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="consumer",
                source_file=native_solid_source,
            )
        )

        assert result["success"] is True
        assert result["node_id"] == "consumer"

        # eval_with_solid_imports used (not eval_with_imports)
        mock_vcad.eval_with_solid_imports.assert_called_once()
        mock_vcad.eval_with_imports.assert_not_called()

        # Verify native mesh data is forwarded
        call_kwargs = mock_vcad.eval_with_solid_imports.call_args.kwargs
        import_0 = call_kwargs["imports"]["import_0"]
        assert import_0["extract"] == "solid"
        assert import_0["source"] == "native_mesh"
        assert import_0["vcad_node_id"] is None
        assert import_0["native_mesh"] == SAMPLE_MESH
        assert import_0["native_mesh"]["positions"] == SAMPLE_MESH["positions"]
        assert import_0["native_mesh"]["indices"] == SAMPLE_MESH["indices"]
        assert import_0["native_mesh"]["normals"] == SAMPLE_MESH["normals"]

    def test_mixed_native_and_vcad_solid_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, mixed_native_vcad_source
    ):
        """Mixed native mesh + vcad-backed solids both use eval_with_solid_imports."""
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "wall",
                    "extract": "solid",
                    "entity_ref": "entity:11111",
                    "injected_symbol": "__vcad_import_0",
                },
                {
                    "import_id": "import_1",
                    "binding_name": "bracket",
                    "extract": "solid",
                    "entity_ref": "entity:22222",
                    "injected_symbol": "__vcad_import_1",
                },
            ],
            "transformed_source": (
                "[let wall __vcad_import_0]\n"
                "[let bracket __vcad_import_1]\n"
                "[cube 1.0 1.0 1.0]"
            ),
        }

        # First resolve: native mesh, second: vcad-backed
        mock_sketchup.send_command.side_effect = [
            {
                "extract": "solid",
                "source": "native_mesh",
                "mesh": SAMPLE_MESH,
            },
            {
                "extract": "solid",
                "source": "vcad",
                "vcad_node_id": "bracket-node",
            },
            {
                "success": True,
                "node_id": "mixed",
                "entity_id": 502,
            },
        ]

        mock_vcad.eval_with_solid_imports.return_value = {
            "obj_path": "/tmp/mixed-native-vcad.dae",
            "volume": 1000.0,
        }

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="mixed",
                source_file=mixed_native_vcad_source,
            )
        )

        assert result["success"] is True

        call_kwargs = mock_vcad.eval_with_solid_imports.call_args.kwargs
        imports = call_kwargs["imports"]

        # Native mesh import
        assert imports["import_0"]["source"] == "native_mesh"
        assert imports["import_0"]["native_mesh"] == SAMPLE_MESH
        assert imports["import_0"]["vcad_node_id"] is None

        # VCAD-backed import
        assert imports["import_1"]["vcad_node_id"] == "bracket-node"
        assert imports["import_1"].get("native_mesh") is None

    def test_native_mesh_with_data_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Native mesh + data imports coexist correctly."""
        src = tmp_path / "native-with-data.skp.oo"
        src.write_text(
            '[let dims [import :dimensions "entity:100"]]\n'
            '[let wall [import :solid "entity:11111"]]\n'
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
                    "binding_name": "wall",
                    "extract": "solid",
                    "entity_ref": "entity:11111",
                    "injected_symbol": "__vcad_import_1",
                },
            ],
            "transformed_source": "[let dims __vcad_import_0]\n[let wall __vcad_import_1]\n[cube 1.0 1.0 1.0]",
        }

        mock_sketchup.send_command.side_effect = [
            {
                "extract": "dimensions",
                "vcad_node_id": None,
                "data": {"width": 100.0, "height": 200.0, "depth": 50.0},
            },
            {
                "extract": "solid",
                "source": "native_mesh",
                "mesh": SAMPLE_MESH,
            },
            {
                "success": True,
                "node_id": "native-data",
                "entity_id": 503,
            },
        ]

        mock_vcad.eval_with_solid_imports.return_value = {
            "obj_path": "/tmp/native-data.dae",
        }

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="native-data",
                source_file=str(src),
            )
        )

        assert result["success"] is True

        call_kwargs = mock_vcad.eval_with_solid_imports.call_args.kwargs
        imports = call_kwargs["imports"]

        # Data import
        assert imports["import_0"]["extract"] == "dimensions"
        assert imports["import_0"]["data"]["width"] == 100.0

        # Native mesh import
        assert imports["import_1"]["extract"] == "solid"
        assert imports["import_1"]["source"] == "native_mesh"
        assert imports["import_1"]["native_mesh"] is not None


# ---------------------------------------------------------------------------
# Native mesh import — error paths
# ---------------------------------------------------------------------------


class TestNativeMeshImportErrors:
    """Test error handling for native mesh imports."""

    def test_non_solid_entity_returns_error(
        self, mock_ctx, mock_vcad, mock_sketchup, native_solid_source
    ):
        """Non-manifold entity requesting :solid returns error from SketchUp."""
        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "wall",
                    "extract": "solid",
                    "entity_ref": "entity:11111",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let wall __vcad_import_0]",
        }

        # SketchUp raises error: entity is not a solid
        mock_sketchup.send_command.side_effect = SketchUpRemoteError(
            code=-32603,
            message="Entity 11111 is not a solid — :solid import unavailable",
        )

        result = json.loads(
            vcad_place_with_imports(
                mock_ctx,
                node_id="bad-native",
                source_file=native_solid_source,
            )
        )

        assert result["success"] is False
        assert result["error_code"] == -32603
        assert result["details"]["error_type"] == "remote"


# ---------------------------------------------------------------------------
# DAG import ref building with native mesh
# ---------------------------------------------------------------------------


class TestBuildImportRefsWithNativeMesh:
    """Test _build_import_refs handles native_mesh imports correctly."""

    def test_native_mesh_import_creates_native_mesh_ref(self):
        """Native mesh import resolved_type is 'native_mesh' with no source_node_id."""
        import_decls = [
            {
                "import_id": "import_0",
                "binding_name": "wall",
                "extract": "solid",
                "entity_ref": "entity:11111",
                "injected_symbol": "__vcad_import_0",
            }
        ]
        resolved_imports = {
            "import_0": {
                "extract": "solid",
                "injected_symbol": "__vcad_import_0",
                "source": "native_mesh",
                "data": None,
                "vcad_node_id": None,
                "native_mesh": SAMPLE_MESH,
                "resolved_type": "native_mesh",
            }
        }

        refs = _build_import_refs(import_decls, resolved_imports)

        assert len(refs) == 1
        assert refs[0].extract == "solid"
        assert refs[0].resolved_type == "native_mesh"
        assert refs[0].source_node_id is None

    def test_mixed_vcad_and_native_mesh_refs(self):
        """Mixed vcad + native_mesh produce correct ref types."""
        import_decls = [
            {
                "import_id": "import_0",
                "binding_name": "wall",
                "extract": "solid",
                "entity_ref": "entity:11111",
                "injected_symbol": "__vcad_import_0",
            },
            {
                "import_id": "import_1",
                "binding_name": "bracket",
                "extract": "solid",
                "entity_ref": "entity:22222",
                "injected_symbol": "__vcad_import_1",
            },
        ]
        resolved_imports = {
            "import_0": {
                "extract": "solid",
                "injected_symbol": "__vcad_import_0",
                "source": "native_mesh",
                "data": None,
                "vcad_node_id": None,
                "native_mesh": SAMPLE_MESH,
                "resolved_type": "native_mesh",
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
        # Native mesh: no DAG dependency
        assert refs[0].extract == "solid"
        assert refs[0].resolved_type == "native_mesh"
        assert refs[0].source_node_id is None
        # VCAD-backed: DAG dependency on bracket-node
        assert refs[1].extract == "solid"
        assert refs[1].resolved_type == "vcad"
        assert refs[1].source_node_id == "bracket-node"

    def test_native_mesh_no_dag_dependency(self):
        """Native mesh imports don't create DAG edges (no source_node_id)."""
        from supex_driver.connection.vcad_dag import VcadDag, VcadNode

        dag = VcadDag()

        # Consumer node imports native mesh (no source_node_id)
        from supex_driver.connection.vcad_dag import ImportRef

        consumer = VcadNode(
            node_id="consumer",
            source_file="/tmp/consumer.skp.oo",
            imports=[
                ImportRef(
                    binding_name="wall",
                    entity_ref="entity:11111",
                    extract="solid",
                    resolved_type="native_mesh",
                    source_node_id=None,
                )
            ],
        )
        dag.add_node(consumer)

        # No downstream dependencies
        downstream = dag.get_downstream("consumer")
        assert downstream == []
