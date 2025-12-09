"""E2E tests for batch screenshot functionality.

Tests for take_batch_screenshots tool with various camera configurations.
"""

from pathlib import Path

from helpers.cli_runner import CLIRunner


class TestBatchScreenshotsBasic:
    """Basic batch screenshot tests."""

    def test_single_zoom_extents_shot(self, populated_model: CLIRunner) -> None:
        """Single screenshot with zoom_extents should succeed."""
        result = populated_model.call_snippet("batch_single_zoom_extents")
        assert result.success, f"Batch screenshot failed: {result.stderr}"

        data = result.json()
        assert data["success"] is True, f"Expected success, got: {data}"
        assert data["total_shots"] == 1
        assert data["successful"] == 1
        assert data["failed"] == 0

        # Verify file was created
        temp_dir = Path(data["temp_dir"])
        expected_file = temp_dir / "test_single_full.png"
        assert expected_file.exists(), f"Expected file {expected_file} to exist"

    def test_multiple_standard_views(self, populated_model: CLIRunner) -> None:
        """Multiple standard view screenshots should all succeed."""
        result = populated_model.call_snippet("batch_multiple_standard_views")
        assert result.success, f"Batch screenshot failed: {result.stderr}"

        data = result.json()
        assert data["success"] is True, f"Expected success, got: {data}"
        assert data["total_shots"] == 3
        assert data["successful"] == 3

        # Verify all files were created
        temp_dir = Path(data["temp_dir"])
        for view in ["front", "top", "iso"]:
            expected_file = temp_dir / f"test_views_{view}.png"
            assert expected_file.exists(), f"Expected file {expected_file} to exist"


class TestBatchScreenshotsCustomCamera:
    """Tests for custom camera configurations."""

    def test_custom_camera_diagonal_view(self, populated_model: CLIRunner) -> None:
        """Custom camera with diagonal view should work."""
        result = populated_model.call_snippet("batch_custom_diagonal_view")
        assert result.success, f"Batch screenshot failed: {result.stderr}"

        data = result.json()
        assert data["success"] is True
        assert data["successful"] == 1

    def test_custom_camera_top_down_view_regression(self, populated_model: CLIRunner) -> None:
        """REGRESSION TEST: Top-down view should not raise parallel vector error.

        This tests the fix for BUG-parallel-vector-top-view.md where camera
        looking straight down would fail with "Up vector cannot be parallel
        to view direction" error.
        """
        result = populated_model.call_snippet("batch_custom_top_down_view")
        assert result.success, f"Top-down view failed (regression): {result.stderr}"

        data = result.json()
        assert data["success"] is True, f"Expected success for top-down view, got: {data}"
        assert data["successful"] == 1

    def test_custom_camera_bottom_up_view(self, populated_model: CLIRunner) -> None:
        """Bottom-up view should also work (parallel vector edge case)."""
        result = populated_model.call_snippet("batch_custom_bottom_up_view")
        assert result.success, f"Bottom-up view failed: {result.stderr}"

        data = result.json()
        assert data["success"] is True

    def test_custom_camera_with_fov(self, populated_model: CLIRunner) -> None:
        """Custom camera with specific FOV."""
        result = populated_model.call_snippet("batch_custom_with_fov")
        assert result.success, f"Custom FOV failed: {result.stderr}"

        data = result.json()
        assert data["success"] is True


class TestBatchScreenshotsErrorHandling:
    """Tests for error handling in batch screenshots."""

    def test_partial_failure_continues(self, populated_model: CLIRunner) -> None:
        """Batch should continue after individual shot failure."""
        result = populated_model.call_snippet("batch_partial_failure")
        assert result.success, f"Eval failed: {result.stderr}"

        data = result.json()
        # Overall success is False because one shot failed
        assert data["success"] is False
        assert data["total_shots"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1

        # Good shots should have files
        temp_dir = Path(data["temp_dir"])
        assert (temp_dir / "test_partial_good1.png").exists()
        assert (temp_dir / "test_partial_good2.png").exists()

    def test_invalid_camera_type_fails_gracefully(self, populated_model: CLIRunner) -> None:
        """Invalid camera type should fail that shot only."""
        result = populated_model.call_snippet("batch_invalid_camera_type")
        assert result.success, f"Eval failed: {result.stderr}"

        data = result.json()
        assert data["successful"] == 1
        assert data["failed"] == 1


class TestBatchScreenshotsCameraRestore:
    """Tests for camera state preservation."""

    def test_camera_restored_after_batch(self, populated_model: CLIRunner) -> None:
        """Original camera should be restored after batch completes."""
        # Get initial camera position
        initial_result = populated_model.call_snippet("batch_get_camera_state")
        assert initial_result.success
        initial_camera = initial_result.json()

        # Take batch screenshots with different camera positions
        batch_result = populated_model.call_snippet("batch_camera_restore_test")
        assert batch_result.success

        # Get camera position after batch
        final_result = populated_model.call_snippet("batch_get_camera_state")
        assert final_result.success
        final_camera = final_result.json()

        # Camera should be restored to initial position (with some tolerance)
        for i in range(3):
            assert abs(initial_camera["eye"][i] - final_camera["eye"][i]) < 0.1, \
                f"Camera eye not restored: {initial_camera['eye']} vs {final_camera['eye']}"


class TestBatchScreenshotsIsolation:
    """Tests for subtree isolation (Hide Rest of Model)."""

    def test_isolation_with_group(self, fresh_model: CLIRunner) -> None:
        """Isolation should work with a group entity."""
        # Create a test group
        create_result = fresh_model.call_snippet("batch_create_test_group")
        assert create_result.success, f"Failed to create test group: {create_result.stderr}"
        group_data = create_result.json()
        group_id = group_data["group_id"]

        # Take screenshot with isolation
        result = fresh_model.call_snippet("batch_with_isolation", group_id)
        assert result.success, f"Isolation batch failed: {result.stderr}"

        data = result.json()
        assert data["success"] is True, f"Expected success, got: {data}"
        assert data["successful"] == 1

        # Verify file was created
        temp_dir = Path(data["temp_dir"])
        expected_file = temp_dir / "test_isolation_isolated.png"
        assert expected_file.exists(), f"Expected file {expected_file} to exist"

    def test_isolation_state_restored(self, fresh_model: CLIRunner) -> None:
        """Isolation state should be restored after batch completes."""
        # Get initial isolation state
        initial_result = fresh_model.call_snippet("batch_get_isolation_state")
        assert initial_result.success
        initial_state = initial_result.json()

        # Create a test group
        create_result = fresh_model.call_snippet("batch_create_test_group")
        assert create_result.success
        group_data = create_result.json()
        group_id = group_data["group_id"]

        # Take screenshot with isolation
        batch_result = fresh_model.call_snippet("batch_with_isolation", group_id)
        assert batch_result.success

        # Get isolation state after batch
        final_result = fresh_model.call_snippet("batch_get_isolation_state")
        assert final_result.success
        final_state = final_result.json()

        # State should be restored
        assert final_state["active_path_nil"] == initial_state["active_path_nil"], \
            "active_path was not restored"
        assert final_state["inactive_hidden"] == initial_state["inactive_hidden"], \
            "InactiveHidden was not restored"

    def test_isolation_invalid_entity_fails_gracefully(self, fresh_model: CLIRunner) -> None:
        """Isolation with invalid entity should fail that shot only."""
        result = fresh_model.call_snippet("batch_isolation_invalid_entity")
        assert result.success, f"Eval failed: {result.stderr}"

        data = result.json()
        # Shot should fail but batch should complete
        assert data["failed"] == 1, f"Expected 1 failed shot, got: {data}"
        assert data["successful"] == 0, f"Expected 0 successful shots, got: {data}"
