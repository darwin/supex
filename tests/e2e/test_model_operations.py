"""Tests for model creation and manipulation."""

import pytest

from helpers.cli_runner import CLIRunner


class TestGeometryCreation:
    """Tests for creating geometry."""

    def test_create_cube(self, fresh_model: CLIRunner) -> None:
        """Create a cube and verify face/edge counts."""
        cli = fresh_model
        result = cli.call_snippet('geom_create_cube')
        assert result.success, f"Failed to create cube: {result.stderr}"
        # A cube has 6 faces and 12 edges
        assert "6" in result.stdout  # faces
        assert "12" in result.stdout  # edges

    def test_create_circle(self, fresh_model: CLIRunner) -> None:
        """Create a circle and verify it exists."""
        cli = fresh_model
        result = cli.call_snippet('geom_create_circle')
        assert result.success, f"Failed to create circle: {result.stderr}"
        # Default circle has 24 segments
        assert "24" in result.stdout

    def test_create_cylinder(self, fresh_model: CLIRunner) -> None:
        """Create a cylinder by extruding a circle."""
        cli = fresh_model
        result = cli.call_snippet('geom_create_cylinder')
        assert result.success, f"Failed to create cylinder: {result.stderr}"
        # Cylinder has 3 faces: top, bottom, and curved surface
        # But SketchUp represents curved surface as multiple faces
        face_count = int(result.stdout.strip())
        assert face_count >= 3


class TestGroups:
    """Tests for group operations."""

    def test_create_group(self, fresh_model: CLIRunner) -> None:
        """Create a group and verify it exists."""
        cli = fresh_model
        result = cli.call_snippet('group_create_named')
        assert result.success
        assert "TestGroup" in result.stdout

    def test_create_nested_groups(self, fresh_model: CLIRunner) -> None:
        """Create nested groups."""
        cli = fresh_model
        result = cli.call_snippet('group_create_nested')
        assert result.success
        assert "Inner" in result.stdout


class TestComponents:
    """Tests for component operations."""

    def test_create_component(self, fresh_model: CLIRunner) -> None:
        """Create a component definition and instance."""
        cli = fresh_model
        result = cli.call_snippet('component_create')
        assert result.success
        assert "TestComponent" in result.stdout

    def test_multiple_component_instances(self, fresh_model: CLIRunner) -> None:
        """Create multiple instances of the same component."""
        cli = fresh_model
        result = cli.call_snippet('component_create_multiple_instances')
        assert result.success
        assert "3" in result.stdout


class TestMaterials:
    """Tests for material operations."""

    def test_create_material(self, fresh_model: CLIRunner) -> None:
        """Create a material and apply it to a face."""
        cli = fresh_model
        result = cli.call_snippet('material_create_and_apply')
        assert result.success
        assert "RedMaterial" in result.stdout

    def test_material_with_alpha(self, fresh_model: CLIRunner) -> None:
        """Create a semi-transparent material."""
        cli = fresh_model
        result = cli.call_snippet('material_create_transparent')
        assert result.success
        assert "0.5" in result.stdout
