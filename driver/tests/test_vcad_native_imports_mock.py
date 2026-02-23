"""Mock-based tests for native SketchUp solid import (CSG scenarios).

Verifies the full flow: SketchUp mesh extraction -> driver mediation ->
sidecar evaluation, with focus on CSG operations (difference, union,
intersection) against native mesh geometry.
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
    vcad_place,
)


# ---------------------------------------------------------------------------
# Sample mesh data — a box (8 vertices, 12 triangles)
# ---------------------------------------------------------------------------

BOX_MESH = {
    "positions": [
        0.0, 0.0, 0.0,
        100.0, 0.0, 0.0,
        100.0, 100.0, 0.0,
        0.0, 100.0, 0.0,
        0.0, 0.0, 100.0,
        100.0, 0.0, 100.0,
        100.0, 100.0, 100.0,
        0.0, 100.0, 100.0,
    ],
    "indices": [
        0, 1, 2, 0, 2, 3,  # bottom
        4, 6, 5, 4, 7, 6,  # top
        0, 4, 5, 0, 5, 1,  # front
        2, 6, 7, 2, 7, 3,  # back
        0, 3, 7, 0, 7, 4,  # left
        1, 5, 6, 1, 6, 2,  # right
    ],
    "normals": [
        0.0, 0.0, -1.0,
        0.0, 0.0, -1.0,
        0.0, 0.0, -1.0,
        0.0, 0.0, -1.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 1.0,
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.request_id = "test-req-native-mock-1"
    return ctx


@pytest.fixture
def mock_vcad():
    with patch("supex_driver.mcp.vcad_tools.get_vcad_connection") as mock_get:
        conn = MagicMock()
        mock_get.return_value = conn
        yield conn


@pytest.fixture
def mock_sketchup():
    with patch("supex_driver.mcp.vcad_tools.get_sketchup_connection") as mock_get:
        conn = MagicMock()
        mock_get.return_value = conn
        yield conn


def _make_source(tmp_path, name, content):
    """Helper to create a .skp.oo source file."""
    src = tmp_path / name
    src.write_text(content)
    return str(src)


def _setup_native_mesh_flow(mock_vcad, mock_sketchup, mesh=None):
    """Common setup for single native mesh import tests."""
    if mesh is None:
        mesh = BOX_MESH

    mock_vcad.extract_imports.return_value = {
        "imports": [
            {
                "import_id": "import_0",
                "binding_name": "native_solid",
                "extracts": ["solid"],
                "source": "host",
                "selector": "entity:55555",
                "injected_symbol": "__vcad_import_0",
            }
        ],
        "transformed_source": "[let native_solid __vcad_import_0]\n[cube 10.0 10.0 10.0]",
    }

    mock_sketchup.send_command.side_effect = [
        {
            "extract": "solid",
            "source": "native_mesh",
            "mesh": mesh,
        },
        {
            "success": True,
            "node_id": "csg-test",
            "entity_id": 600,
            "definition_name": "vcad_csg_test",
        },
    ]


# ---------------------------------------------------------------------------
# CSG operations with native mesh
# ---------------------------------------------------------------------------


class TestNativeMeshCSG:
    """Test CSG operations (difference, union, intersection) with native mesh."""

    def test_difference_with_native_mesh(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Difference: subtract native mesh from parametric cube."""
        src = _make_source(
            tmp_path,
            "diff.skp.oo",
            '[let wall [import :host "entity:55555" :solid]]\n'
            "[pipe [cube 200.0 200.0 200.0]\n"
            "  [difference wall]]",
        )

        _setup_native_mesh_flow(mock_vcad, mock_sketchup)
        mock_vcad.eval_with_imports.return_value = {
            "mesh_path": "/tmp/diff-native.dae",
            "volume": 7000000.0,
            "surface_area": 240000.0,
        }

        result = json.loads(
            vcad_place(
                mock_ctx, node_id="csg-test", source_file=src
            )
        )

        assert result["success"] is True

        # Verify mesh forwarded to sidecar
        call_kwargs = mock_vcad.eval_with_imports.call_args.kwargs
        imp = call_kwargs["imports"]["import_0"]
        assert imp["source"] == "native_mesh"
        assert imp["native_mesh"]["positions"] == BOX_MESH["positions"]

    def test_union_with_native_mesh(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Union: combine native mesh with parametric cube."""
        src = _make_source(
            tmp_path,
            "union.skp.oo",
            '[let wall [import :host "entity:55555" :solid]]\n'
            "[pipe [cube 200.0 200.0 200.0]\n"
            "  [union wall]]",
        )

        _setup_native_mesh_flow(mock_vcad, mock_sketchup)
        mock_vcad.eval_with_imports.return_value = {
            "mesh_path": "/tmp/union-native.dae",
            "volume": 9000000.0,
        }

        result = json.loads(
            vcad_place(
                mock_ctx, node_id="csg-test", source_file=src
            )
        )

        assert result["success"] is True
        mock_vcad.eval_with_imports.assert_called_once()

    def test_intersection_with_native_mesh(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Intersection: intersect native mesh with parametric cube."""
        src = _make_source(
            tmp_path,
            "intersect.skp.oo",
            '[let wall [import :host "entity:55555" :solid]]\n'
            "[pipe [cube 200.0 200.0 200.0]\n"
            "  [intersection wall]]",
        )

        _setup_native_mesh_flow(mock_vcad, mock_sketchup)
        mock_vcad.eval_with_imports.return_value = {
            "mesh_path": "/tmp/intersect-native.dae",
            "volume": 1000000.0,
        }

        result = json.loads(
            vcad_place(
                mock_ctx, node_id="csg-test", source_file=src
            )
        )

        assert result["success"] is True
        mock_vcad.eval_with_imports.assert_called_once()


# ---------------------------------------------------------------------------
# Full flow: mesh data integrity
# ---------------------------------------------------------------------------


class TestNativeMeshDataIntegrity:
    """Verify mesh data is forwarded without modification."""

    def test_mesh_positions_preserved(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """All position values are forwarded exactly."""
        src = _make_source(
            tmp_path,
            "preserve.skp.oo",
            '[let obj [import :host "entity:55555" :solid]]\n[obj]',
        )

        _setup_native_mesh_flow(mock_vcad, mock_sketchup)
        mock_vcad.eval_with_imports.return_value = {
            "mesh_path": "/tmp/preserve.dae",
        }

        vcad_place(
            mock_ctx, node_id="csg-test", source_file=src
        )

        call_kwargs = mock_vcad.eval_with_imports.call_args.kwargs
        mesh = call_kwargs["imports"]["import_0"]["native_mesh"]
        assert mesh["positions"] == BOX_MESH["positions"]
        assert mesh["indices"] == BOX_MESH["indices"]
        assert mesh["normals"] == BOX_MESH["normals"]

    def test_empty_normals_forwarded(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Mesh with empty normals array is still forwarded."""
        src = _make_source(
            tmp_path,
            "no-normals.skp.oo",
            '[let obj [import :host "entity:55555" :solid]]\n[obj]',
        )

        mesh_no_normals = {
            "positions": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            "indices": [0, 1, 2],
            "normals": [],
        }
        _setup_native_mesh_flow(mock_vcad, mock_sketchup, mesh=mesh_no_normals)
        mock_vcad.eval_with_imports.return_value = {
            "mesh_path": "/tmp/no-normals.dae",
        }

        vcad_place(
            mock_ctx, node_id="csg-test", source_file=src
        )

        call_kwargs = mock_vcad.eval_with_imports.call_args.kwargs
        mesh = call_kwargs["imports"]["import_0"]["native_mesh"]
        assert mesh["normals"] == []


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


class TestNativeMeshErrors:
    """Test error scenarios for native mesh imports."""

    def test_non_manifold_entity_error(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Non-manifold (non-solid) entity raises error from SketchUp bridge."""
        src = _make_source(
            tmp_path,
            "non-solid.skp.oo",
            '[let wall [import :host "entity:99999" :solid]]\n[wall]',
        )

        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "wall",
                    "extracts": ["solid"],
                    "source": "host",
                    "selector": "entity:99999",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let wall __vcad_import_0]",
        }

        mock_sketchup.send_command.side_effect = SketchUpRemoteError(
            code=-32603,
            message="Entity 99999 is not a solid — :solid import unavailable",
        )

        result = json.loads(
            vcad_place(
                mock_ctx, node_id="non-solid", source_file=src
            )
        )

        assert result["success"] is False
        assert "not a solid" in result["error"]

    def test_sidecar_rejects_invalid_mesh(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Sidecar returns error if mesh data is invalid."""
        src = _make_source(
            tmp_path,
            "bad-mesh.skp.oo",
            '[let obj [import :host "entity:55555" :solid]]\n[obj]',
        )

        _setup_native_mesh_flow(mock_vcad, mock_sketchup)
        mock_vcad.eval_with_imports.side_effect = VCADRemoteError(
            code=-32000,
            message="INVALID_MESH: native mesh has zero triangles",
            data={"error_code": "INVALID_MESH"},
        )

        result = json.loads(
            vcad_place(
                mock_ctx, node_id="bad-mesh", source_file=src
            )
        )

        assert result["success"] is False
        assert result["error_code"] == -32000

    def test_multiple_native_mesh_imports(
        self, mock_ctx, mock_vcad, mock_sketchup, tmp_path
    ):
        """Multiple native mesh imports in same source all forwarded correctly."""
        src = _make_source(
            tmp_path,
            "multi-native.skp.oo",
            '[let a [import :host "entity:11111" :solid]]\n'
            '[let b [import :host "entity:22222" :solid]]\n'
            "[pipe [cube 100.0 100.0 100.0]\n"
            "  [difference a]\n"
            "  [union b]]",
        )

        mesh_a = {
            "positions": [0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 5.0, 10.0, 0.0],
            "indices": [0, 1, 2],
            "normals": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        }
        mesh_b = {
            "positions": [50.0, 50.0, 0.0, 60.0, 50.0, 0.0, 55.0, 60.0, 0.0],
            "indices": [0, 1, 2],
            "normals": [0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0],
        }

        mock_vcad.extract_imports.return_value = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "a",
                    "extracts": ["solid"],
                    "source": "host",
                    "selector": "entity:11111",
                    "injected_symbol": "__vcad_import_0",
                },
                {
                    "import_id": "import_1",
                    "binding_name": "b",
                    "extracts": ["solid"],
                    "source": "host",
                    "selector": "entity:22222",
                    "injected_symbol": "__vcad_import_1",
                },
            ],
            "transformed_source": (
                "[let a __vcad_import_0]\n"
                "[let b __vcad_import_1]\n"
                "[cube 1.0 1.0 1.0]"
            ),
        }

        mock_sketchup.send_command.side_effect = [
            {"extract": "solid", "source": "native_mesh", "mesh": mesh_a},
            {"extract": "solid", "source": "native_mesh", "mesh": mesh_b},
            {
                "success": True,
                "node_id": "multi-native",
                "entity_id": 700,
            },
        ]

        mock_vcad.eval_with_imports.return_value = {
            "mesh_path": "/tmp/multi-native.dae",
            "volume": 500000.0,
        }

        result = json.loads(
            vcad_place(
                mock_ctx, node_id="multi-native", source_file=src
            )
        )

        assert result["success"] is True

        call_kwargs = mock_vcad.eval_with_imports.call_args.kwargs
        imports = call_kwargs["imports"]
        assert imports["import_0"]["native_mesh"] == mesh_a
        assert imports["import_1"]["native_mesh"] == mesh_b
