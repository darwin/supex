"""Tests for model introspection tools."""

import pytest

from helpers.cli_runner import CLIRunner


class TestModelInfo:
    """Tests for get_model_info functionality."""

    def test_empty_model_info(self, fresh_model: CLIRunner) -> None:
        """Empty model should report zero entities."""
        cli = fresh_model
        result = cli.info()
        assert result.success, f"Info failed: {result.stderr}"
        # Check that we get some output
        assert result.stdout.strip()

    def test_model_info_after_geometry(self, fresh_model: CLIRunner) -> None:
        """Model info should reflect created geometry."""
        cli = fresh_model

        # Create some geometry
        cli.call_snippet('geom_add_face')

        result = cli.info()
        assert result.success
        # Should show at least 1 face
        assert result.stdout.strip()


class TestListEntities:
    """Tests for list_entities functionality."""

    def test_list_entities_empty(self, fresh_model: CLIRunner) -> None:
        """Empty model should list no entities."""
        cli = fresh_model
        result = cli.entities()
        assert result.success

    def test_list_faces(self, fresh_model: CLIRunner) -> None:
        """List only faces after creating geometry."""
        cli = fresh_model

        # Create a face
        cli.call_snippet('geom_add_face')

        result = cli.entities("faces")
        assert result.success

    def test_list_edges(self, fresh_model: CLIRunner) -> None:
        """List only edges."""
        cli = fresh_model

        # Create edges
        cli.call_snippet('geom_add_edges')

        result = cli.entities("edges")
        assert result.success

    def test_list_groups(self, fresh_model: CLIRunner) -> None:
        """List only groups."""
        cli = fresh_model

        # Create a group
        cli.call_snippet('group_create_with_line')

        result = cli.entities("groups")
        assert result.success


class TestSelection:
    """Tests for selection functionality."""

    def test_empty_selection(self, fresh_model: CLIRunner) -> None:
        """Empty selection should return empty/zero."""
        cli = fresh_model
        result = cli.selection()
        assert result.success

    def test_select_entity(self, fresh_model: CLIRunner) -> None:
        """Select an entity and verify it's selected."""
        cli = fresh_model

        # Create and select a face
        result = cli.call_snippet('selection_add_face')
        assert result.success
        assert "1" in result.stdout

        # Verify through selection command
        sel_result = cli.selection()
        assert sel_result.success


class TestLayers:
    """Tests for layer/tag functionality."""

    def test_default_layer_exists(self, cli: CLIRunner) -> None:
        """Default layer (Layer0/Untagged) should exist."""
        result = cli.layers()
        assert result.success
        # There should be at least one layer

    def test_create_layer(self, fresh_model: CLIRunner) -> None:
        """Create a new layer/tag."""
        cli = fresh_model

        result = cli.call_snippet('layer_create')
        assert result.success
        assert "TestLayer" in result.stdout


class TestMaterialsIntrospection:
    """Tests for materials introspection."""

    def test_no_materials_initially(self, fresh_model: CLIRunner) -> None:
        """Fresh model may have no custom materials."""
        cli = fresh_model
        result = cli.materials()
        assert result.success

    def test_materials_after_creation(self, fresh_model: CLIRunner) -> None:
        """Materials list should include created materials."""
        cli = fresh_model

        result = cli.call_snippet('material_create_blue')
        assert result.success

        # Check via materials command
        mat_result = cli.materials()
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
        """Set camera position and verify."""
        result = cli.call_snippet('camera_set_position')
        assert result.success
        assert "10" in result.stdout
