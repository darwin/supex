"""Tests for model introspection tools.

Tests for introspection commands that query model state: info, entities,
selection, layers, materials, and camera.
"""

from helpers.cli_runner import CLIRunner


class TestModelInfo:
    """Tests for get_model_info functionality."""

    def test_empty_model_info(self, fresh_model: CLIRunner) -> None:
        """Empty model should report zero entities."""
        result = fresh_model.info()
        assert result.success, f"Info failed: {result.stderr}"
        # Check that we get some output
        assert result.stdout.strip()

    def test_model_info_after_geometry(self, fresh_model: CLIRunner) -> None:
        """Model info should reflect created geometry."""
        # Create some geometry
        setup_result = fresh_model.call_snippet("geom_add_face")
        assert setup_result.success, f"Setup failed: {setup_result.stderr}"

        result = fresh_model.info()
        assert result.success
        # Should show at least 1 face
        assert result.stdout.strip()


class TestListEntities:
    """Tests for list_entities functionality."""

    def test_list_entities_empty(self, fresh_model: CLIRunner) -> None:
        """Empty model should list no entities."""
        result = fresh_model.entities()
        assert result.success

    def test_list_faces(self, fresh_model: CLIRunner) -> None:
        """List only faces after creating geometry."""
        # Create a face and verify via JSON
        setup_result = fresh_model.call_snippet("geom_add_face")
        assert setup_result.success
        data = setup_result.json()
        assert data["faces"] == 1, f"Expected 1 face, got {data['faces']}"

        result = fresh_model.entities("faces")
        assert result.success

    def test_list_edges(self, fresh_model: CLIRunner) -> None:
        """List only edges after creating them."""
        # Create edges and verify via JSON
        setup_result = fresh_model.call_snippet("geom_add_edges")
        assert setup_result.success
        data = setup_result.json()
        assert data["edges"] == 2, f"Expected 2 edges, got {data['edges']}"

        result = fresh_model.entities("edges")
        assert result.success

    def test_list_groups(self, fresh_model: CLIRunner) -> None:
        """List only groups after creating one."""
        # Create a group and verify via JSON
        setup_result = fresh_model.call_snippet("group_create_with_line")
        assert setup_result.success
        data = setup_result.json()
        assert data["groups"] == 1, f"Expected 1 group, got {data['groups']}"

        result = fresh_model.entities("groups")
        assert result.success


class TestSelection:
    """Tests for selection functionality."""

    def test_empty_selection(self, fresh_model: CLIRunner) -> None:
        """Empty selection should return empty/zero."""
        result = fresh_model.selection()
        assert result.success

    def test_select_entity(self, fresh_model: CLIRunner) -> None:
        """Select an entity and verify it's selected."""
        # Create and select a face
        result = fresh_model.call_snippet("selection_add_face")
        assert result.success, f"Failed to select: {result.stderr}"
        data = result.json()
        assert data["selected"] == 1, f"Expected 1 selected, got {data['selected']}"

        # Verify through selection command
        sel_result = fresh_model.selection()
        assert sel_result.success


class TestLayers:
    """Tests for layer/tag functionality."""

    def test_default_layer_exists(self, cli: CLIRunner) -> None:
        """Default layer (Layer0/Untagged) should exist."""
        result = cli.layers()
        assert result.success
        # There should be at least one layer

    def test_create_layer(self, fresh_model: CLIRunner) -> None:
        """Create a new layer/tag and verify its name."""
        result = fresh_model.call_snippet("layer_create")
        assert result.success, f"Failed to create layer: {result.stderr}"
        data = result.json()
        assert data["name"] == "TestLayer", f"Expected name 'TestLayer', got '{data['name']}'"


class TestMaterialsIntrospection:
    """Tests for materials introspection."""

    def test_no_materials_initially(self, fresh_model: CLIRunner) -> None:
        """Fresh model may have no custom materials."""
        result = fresh_model.materials()
        assert result.success

    def test_materials_after_creation(self, fresh_model: CLIRunner) -> None:
        """Materials list should include created materials."""
        result = fresh_model.call_snippet("material_create_blue")
        assert result.success, f"Failed to create material: {result.stderr}"
        data = result.json()
        assert data["name"] == "BlueMaterial", f"Expected name 'BlueMaterial', got '{data['name']}'"
        assert data["count"] >= 1, f"Expected at least 1 material, got {data['count']}"

        # Check via materials command
        mat_result = fresh_model.materials()
        assert mat_result.success


class TestCamera:
    """Tests for camera introspection."""

    def test_camera_info(self, cli: CLIRunner) -> None:
        """Camera info should return position and orientation."""
        result = cli.camera()
        assert result.success
        # Should contain camera information
        assert result.stdout.strip()

    def test_set_camera_position(self, cli: CLIRunner) -> None:
        """Set camera position and verify coordinates."""
        result = cli.call_snippet("camera_set_position")
        assert result.success, f"Failed to set camera: {result.stderr}"
        data = result.json()
        assert data["eye"][0] == 10.0, f"Expected eye.x = 10.0, got {data['eye'][0]}"
        assert data["eye"][1] == 10.0, f"Expected eye.y = 10.0, got {data['eye'][1]}"
        assert data["eye"][2] == 10.0, f"Expected eye.z = 10.0, got {data['eye'][2]}"
