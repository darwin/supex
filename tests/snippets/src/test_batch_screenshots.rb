# frozen_string_literal: true

# Ruby snippets for test_batch_screenshots.py
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts
# All functions return JSON strings for structured assertions

require 'json'

module SupexTestSnippets
  # Helper to get temp directory for batch screenshot tests
  def self.batch_screenshot_temp_dir
    dir = File.join(Dir.tmpdir, 'supex_e2e_batch_screenshots')
    FileUtils.mkdir_p(dir)
    dir
  end

  # Single screenshot with default camera (standard_view iso + zoom_extents)
  # @return [String] JSON with success status and file info
  def self.batch_single_zoom_extents
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{ 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'full' }],
      'output_dir' => temp_dir,
      'base_name' => 'test_single',
      'width' => 800,
      'height' => 600
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Multiple standard view screenshots
  # @return [String] JSON with success status
  def self.batch_multiple_standard_views
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'front' }, 'name' => 'front' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'top' }, 'name' => 'top' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'iso' }
      ],
      'output_dir' => temp_dir,
      'base_name' => 'test_views',
      'width' => 640,
      'height' => 480
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Custom camera with diagonal view
  # @return [String] JSON with success status
  def self.batch_custom_diagonal_view
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{
        'camera' => { 'type' => 'custom', 'eye' => [100, 100, 100], 'target' => [0, 0, 0] },
        'name' => 'diagonal'
      }],
      'output_dir' => temp_dir,
      'base_name' => 'test_custom',
      'width' => 800,
      'height' => 600
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # REGRESSION TEST: Top-down view (parallel vector bug fix)
  # Camera looking straight down - eye and target have same X,Y
  # @return [String] JSON with success status
  def self.batch_custom_top_down_view
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{
        'camera' => { 'type' => 'custom', 'eye' => [50, 50, 200], 'target' => [50, 50, 0] },
        'name' => 'top_down'
      }],
      'output_dir' => temp_dir,
      'base_name' => 'test_topdown',
      'width' => 800,
      'height' => 600
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Bottom-up view (parallel vector edge case)
  # @return [String] JSON with success status
  def self.batch_custom_bottom_up_view
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{
        'camera' => { 'type' => 'custom', 'eye' => [50, 50, -100], 'target' => [50, 50, 50] },
        'name' => 'bottom_up'
      }],
      'output_dir' => temp_dir,
      'base_name' => 'test_bottomup',
      'width' => 800,
      'height' => 600
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Custom camera with specific FOV
  # @return [String] JSON with success status
  def self.batch_custom_with_fov
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{
        'camera' => {
          'type' => 'custom',
          'eye' => [100, 100, 100],
          'target' => [0, 0, 0],
          'fov' => 60.0
        },
        'name' => 'wide_fov'
      }],
      'output_dir' => temp_dir,
      'base_name' => 'test_fov',
      'width' => 800,
      'height' => 600
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Partial failure test - one shot with invalid entity ID
  # @return [String] JSON with success=false, successful=2, failed=1
  def self.batch_partial_failure
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'good1' },
        { 'camera' => { 'type' => 'zoom_entity', 'entity_ids' => [999_999] }, 'name' => 'bad' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'good2' }
      ],
      'output_dir' => temp_dir,
      'base_name' => 'test_partial',
      'width' => 640,
      'height' => 480
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Invalid camera type test
  # @return [String] JSON with successful=1, failed=1
  def self.batch_invalid_camera_type
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [
        { 'camera' => { 'type' => 'nonexistent_type' }, 'name' => 'invalid' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'valid' }
      ],
      'output_dir' => temp_dir,
      'base_name' => 'test_invalid',
      'width' => 640,
      'height' => 480
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Get current camera state for restore test
  # @return [String] JSON with eye and target arrays
  def self.batch_get_camera_state
    camera = Sketchup.active_model.active_view.camera
    {
      eye: camera.eye.to_a,
      target: camera.target.to_a
    }.to_json
  end

  # Camera restore test - takes shots and restores camera
  # @return [String] JSON with success status
  def self.batch_camera_restore_test
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'top' }, 'name' => 'top' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'front' }, 'name' => 'front' }
      ],
      'output_dir' => temp_dir,
      'base_name' => 'test_restore',
      'width' => 640,
      'height' => 480,
      'restore_camera' => true
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # ==========================================================================
  # Isolation Tests (Hide Rest of Model)
  # ==========================================================================

  # Create a test group and return its entity ID
  # @return [String] JSON with group_id
  def self.batch_create_test_group
    model = Sketchup.active_model
    model.start_operation('Create Test Group', true)

    # Create a group with some geometry
    group = model.entities.add_group
    group.name = 'IsolationTestGroup'
    # Add a simple face inside the group
    pts = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(1.m, 0, 0),
      Geom::Point3d.new(1.m, 1.m, 0),
      Geom::Point3d.new(0, 1.m, 0)
    ]
    group.entities.add_face(pts)

    model.commit_operation

    { group_id: group.entityID, name: group.name }.to_json
  end

  # Test batch screenshot with isolation
  # @param group_id [Integer] entity ID of group to isolate
  # @return [String] JSON with success status
  def self.batch_with_isolation(group_id)
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{
        'camera' => { 'type' => 'standard_view', 'view' => 'iso' },
        'isolate' => group_id,
        'name' => 'isolated'
      }],
      'output_dir' => temp_dir,
      'base_name' => 'test_isolation',
      'width' => 800,
      'height' => 600
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end

  # Get current isolation state (for verifying restore)
  # @return [String] JSON with active_path and inactive_hidden
  def self.batch_get_isolation_state
    model = Sketchup.active_model
    {
      active_path_nil: model.active_path.nil?,
      inactive_hidden: model.rendering_options['InactiveHidden']
    }.to_json
  end

  # Test isolation with invalid entity (should fail gracefully)
  # @return [String] JSON with success=false
  def self.batch_isolation_invalid_entity
    temp_dir = batch_screenshot_temp_dir
    result = SupexRuntime::BatchScreenshot.execute(
      'shots' => [{
        'camera' => { 'type' => 'standard_view', 'view' => 'iso' },
        'isolate' => 999_999_999, # Non-existent entity
        'name' => 'should_fail'
      }],
      'output_dir' => temp_dir,
      'base_name' => 'test_invalid_isolation',
      'width' => 640,
      'height' => 480
    )
    result[:temp_dir] = temp_dir
    result.to_json
  end
end
