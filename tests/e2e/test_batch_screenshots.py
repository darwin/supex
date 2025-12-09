"""E2E tests for batch screenshot functionality.

Tests for take_batch_screenshots tool with various camera configurations.
"""

import json
import os
from pathlib import Path

from helpers.cli_runner import CLIRunner


def get_batch_screenshots_temp_dir() -> Path:
    """Get temp directory for batch screenshot tests."""
    project_root = Path(__file__).parent.parent.parent
    temp_dir = project_root / ".tmp" / "tests" / "e2e" / "batch_screenshots"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


class TestBatchScreenshotsBasic:
    """Basic batch screenshot tests."""

    def test_single_zoom_extents_shot(self, populated_model: CLIRunner) -> None:
        """Single screenshot with zoom_extents should succeed."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{ 'camera' => {{ 'type' => 'zoom_extents' }}, 'name' => 'full' }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_single',
          'width' => 800,
          'height' => 600
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Batch screenshot failed: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["success"] is True, f"Expected success, got: {data}"
        assert data["total_shots"] == 1
        assert data["successful"] == 1
        assert data["failed"] == 0

        # Verify file was created
        expected_file = temp_dir / "test_single_full.png"
        assert expected_file.exists(), f"Expected file {expected_file} to exist"

    def test_multiple_standard_views(self, populated_model: CLIRunner) -> None:
        """Multiple standard view screenshots should all succeed."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{ 'camera' => {{ 'type' => 'standard_view', 'view' => 'front' }}, 'name' => 'front' }},
            {{ 'camera' => {{ 'type' => 'standard_view', 'view' => 'top' }}, 'name' => 'top' }},
            {{ 'camera' => {{ 'type' => 'standard_view', 'view' => 'iso' }}, 'name' => 'iso' }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_views',
          'width' => 640,
          'height' => 480
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Batch screenshot failed: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["success"] is True, f"Expected success, got: {data}"
        assert data["total_shots"] == 3
        assert data["successful"] == 3

        # Verify all files were created
        for view in ["front", "top", "iso"]:
            expected_file = temp_dir / f"test_views_{view}.png"
            assert expected_file.exists(), f"Expected file {expected_file} to exist"


class TestBatchScreenshotsCustomCamera:
    """Tests for custom camera configurations."""

    def test_custom_camera_diagonal_view(self, populated_model: CLIRunner) -> None:
        """Custom camera with diagonal view should work."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{
              'camera' => {{
                'type' => 'custom',
                'eye' => [100, 100, 100],
                'target' => [0, 0, 0]
              }},
              'name' => 'diagonal'
            }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_custom',
          'width' => 800,
          'height' => 600
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Batch screenshot failed: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["successful"] == 1

    def test_custom_camera_top_down_view_regression(self, populated_model: CLIRunner) -> None:
        """REGRESSION TEST: Top-down view should not raise parallel vector error.

        This tests the fix for BUG-parallel-vector-top-view.md where camera
        looking straight down would fail with "Up vector cannot be parallel
        to view direction" error.
        """
        temp_dir = get_batch_screenshots_temp_dir()

        # Camera looking straight down - eye and target have same X,Y
        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{
              'camera' => {{
                'type' => 'custom',
                'eye' => [50, 50, 200],
                'target' => [50, 50, 0]
              }},
              'name' => 'top_down'
            }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_topdown',
          'width' => 800,
          'height' => 600
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Top-down view failed (regression): {result.stderr}"

        data = json.loads(result.stdout)
        assert data["success"] is True, f"Expected success for top-down view, got: {data}"
        assert data["successful"] == 1

    def test_custom_camera_bottom_up_view(self, populated_model: CLIRunner) -> None:
        """Bottom-up view should also work (parallel vector edge case)."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{
              'camera' => {{
                'type' => 'custom',
                'eye' => [50, 50, -100],
                'target' => [50, 50, 50]
              }},
              'name' => 'bottom_up'
            }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_bottomup',
          'width' => 800,
          'height' => 600
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Bottom-up view failed: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["success"] is True

    def test_custom_camera_with_fov(self, populated_model: CLIRunner) -> None:
        """Custom camera with specific FOV."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{
              'camera' => {{
                'type' => 'custom',
                'eye' => [100, 100, 100],
                'target' => [0, 0, 0],
                'fov' => 60.0
              }},
              'name' => 'wide_fov'
            }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_fov',
          'width' => 800,
          'height' => 600
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Custom FOV failed: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["success"] is True


class TestBatchScreenshotsErrorHandling:
    """Tests for error handling in batch screenshots."""

    def test_partial_failure_continues(self, populated_model: CLIRunner) -> None:
        """Batch should continue after individual shot failure."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{ 'camera' => {{ 'type' => 'zoom_extents' }}, 'name' => 'good1' }},
            {{ 'camera' => {{ 'type' => 'zoom_entity', 'entity_ids' => [999999] }}, 'name' => 'bad' }},
            {{ 'camera' => {{ 'type' => 'zoom_extents' }}, 'name' => 'good2' }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_partial',
          'width' => 640,
          'height' => 480
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Eval failed: {result.stderr}"

        data = json.loads(result.stdout)
        # Overall success is False because one shot failed
        assert data["success"] is False
        assert data["total_shots"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1

        # Good shots should have files
        assert (temp_dir / "test_partial_good1.png").exists()
        assert (temp_dir / "test_partial_good2.png").exists()

    def test_invalid_camera_type_fails_gracefully(self, populated_model: CLIRunner) -> None:
        """Invalid camera type should fail that shot only."""
        temp_dir = get_batch_screenshots_temp_dir()

        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{ 'camera' => {{ 'type' => 'nonexistent_type' }}, 'name' => 'invalid' }},
            {{ 'camera' => {{ 'type' => 'zoom_extents' }}, 'name' => 'valid' }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_invalid',
          'width' => 640,
          'height' => 480
        }}).to_json
        """
        result = populated_model.eval(code)
        assert result.success, f"Eval failed: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["successful"] == 1
        assert data["failed"] == 1


class TestBatchScreenshotsCameraRestore:
    """Tests for camera state preservation."""

    def test_camera_restored_after_batch(self, populated_model: CLIRunner) -> None:
        """Original camera should be restored after batch completes."""
        temp_dir = get_batch_screenshots_temp_dir()

        # Get initial camera position
        initial_result = populated_model.eval("""
            camera = Sketchup.active_model.active_view.camera
            { eye: camera.eye.to_a, target: camera.target.to_a }.to_json
        """)
        assert initial_result.success
        initial_camera = json.loads(initial_result.stdout)

        # Take batch screenshots with different camera positions
        code = f"""
        SupexRuntime::BatchScreenshot.execute({{
          'shots' => [
            {{ 'camera' => {{ 'type' => 'standard_view', 'view' => 'top' }}, 'name' => 'top' }},
            {{ 'camera' => {{ 'type' => 'standard_view', 'view' => 'front' }}, 'name' => 'front' }}
          ],
          'output_dir' => '{temp_dir}',
          'base_name' => 'test_restore',
          'width' => 640,
          'height' => 480,
          'restore_camera' => true
        }}).to_json
        """
        batch_result = populated_model.eval(code)
        assert batch_result.success

        # Get camera position after batch
        final_result = populated_model.eval("""
            camera = Sketchup.active_model.active_view.camera
            { eye: camera.eye.to_a, target: camera.target.to_a }.to_json
        """)
        assert final_result.success
        final_camera = json.loads(final_result.stdout)

        # Camera should be restored to initial position (with some tolerance)
        for i in range(3):
            assert abs(initial_camera["eye"][i] - final_camera["eye"][i]) < 0.1, \
                f"Camera eye not restored: {initial_camera['eye']} vs {final_camera['eye']}"
