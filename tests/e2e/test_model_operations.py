"""Tests for model creation and manipulation.

All tests use JSON assertions for structured validation of Ruby snippet outputs.
"""

from helpers.cli_runner import CLIRunner


class TestGeometryCreation:
    """Tests for creating geometry."""

    def test_create_cube(self, fresh_model: CLIRunner) -> None:
        """Create a cube and verify face/edge counts."""
        result = fresh_model.call_snippet("geom_create_cube")
        assert result.success, f"Failed to create cube: {result.stderr}"
        data = result.json()
        assert data["faces"] == 6, f"Cube should have 6 faces, got {data['faces']}"
        assert data["edges"] == 12, f"Cube should have 12 edges, got {data['edges']}"

    def test_create_circle(self, fresh_model: CLIRunner) -> None:
        """Create a circle and verify segment count."""
        result = fresh_model.call_snippet("geom_create_circle")
        assert result.success, f"Failed to create circle: {result.stderr}"
        data = result.json()
        assert data["segments"] == 24, f"Circle should have 24 segments, got {data['segments']}"

    def test_create_cylinder(self, fresh_model: CLIRunner) -> None:
        """Create a cylinder by extruding a circle."""
        result = fresh_model.call_snippet("geom_create_cylinder")
        assert result.success, f"Failed to create cylinder: {result.stderr}"
        data = result.json()
        # Cylinder has top, bottom, and curved surface (multiple faces)
        assert data["faces"] >= 3, f"Cylinder should have >= 3 faces, got {data['faces']}"


class TestGroups:
    """Tests for group operations."""

    def test_create_group(self, fresh_model: CLIRunner) -> None:
        """Create a named group and verify its name."""
        result = fresh_model.call_snippet("group_create_named")
        assert result.success, f"Failed to create group: {result.stderr}"
        data = result.json()
        assert data["name"] == "TestGroup", f"Expected name 'TestGroup', got '{data['name']}'"

    def test_create_nested_groups(self, fresh_model: CLIRunner) -> None:
        """Create nested groups and verify structure."""
        result = fresh_model.call_snippet("group_create_nested")
        assert result.success, f"Failed to create nested groups: {result.stderr}"
        data = result.json()
        assert data["outer"] == "Outer", f"Expected outer name 'Outer', got '{data['outer']}'"
        assert data["inner"] == "Inner", f"Expected inner name 'Inner', got '{data['inner']}'"


class TestComponents:
    """Tests for component operations."""

    def test_create_component(self, fresh_model: CLIRunner) -> None:
        """Create a component definition and instance."""
        result = fresh_model.call_snippet("component_create")
        assert result.success, f"Failed to create component: {result.stderr}"
        data = result.json()
        assert data["name"] == "TestComponent", f"Expected name 'TestComponent', got '{data['name']}'"

    def test_multiple_component_instances(self, fresh_model: CLIRunner) -> None:
        """Create multiple instances of the same component."""
        result = fresh_model.call_snippet("component_create_multiple_instances")
        assert result.success, f"Failed to create instances: {result.stderr}"
        data = result.json()
        assert data["instances"] == 3, f"Expected 3 instances, got {data['instances']}"


class TestMaterials:
    """Tests for material operations."""

    def test_create_material(self, fresh_model: CLIRunner) -> None:
        """Create a material and apply it to a face."""
        result = fresh_model.call_snippet("material_create_and_apply")
        assert result.success, f"Failed to create material: {result.stderr}"
        data = result.json()
        assert data["name"] == "RedMaterial", f"Expected name 'RedMaterial', got '{data['name']}'"

    def test_material_with_alpha(self, fresh_model: CLIRunner) -> None:
        """Create a semi-transparent material."""
        result = fresh_model.call_snippet("material_create_transparent")
        assert result.success, f"Failed to create transparent material: {result.stderr}"
        data = result.json()
        assert data["name"] == "GlassMaterial", f"Expected name 'GlassMaterial', got '{data['name']}'"
        assert data["alpha"] == 0.5, f"Expected alpha 0.5, got {data['alpha']}"
