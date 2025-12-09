# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/batch_screenshot'

class TestBatchScreenshot < Minitest::Test
  def setup
    UI.clear_timers
    UI.reset_ui_mocks
    SupexRuntime::Utils.clear_console_output
    Sketchup.reset_mocks

    @mock_model = Sketchup.active_model
    @mock_view = @mock_model.active_view

    # Create temp directory for test outputs
    @test_output_dir = File.join(Dir.tmpdir, 'supex_test_screenshots')
    FileUtils.mkdir_p(@test_output_dir)
  end

  def teardown
    FileUtils.rm_rf(@test_output_dir) if @test_output_dir && File.exist?(@test_output_dir)
    Sketchup.reset_mocks
  end

  # ==========================================================================
  # Basic Functionality Tests
  # ==========================================================================

  def test_execute_returns_error_without_model
    # Temporarily make active_model return nil
    Sketchup.force_no_model = true

    result = SupexRuntime::BatchScreenshot.execute({ 'shots' => [{}] })

    assert_equal false, result[:success]
    assert_match(/no active model/i, result[:error])
  ensure
    Sketchup.force_no_model = false
  end

  def test_execute_returns_error_without_shots
    result = SupexRuntime::BatchScreenshot.execute({})

    assert_equal false, result[:success]
    assert_match(/no shots/i, result[:error])
  end

  def test_execute_returns_error_with_empty_shots
    result = SupexRuntime::BatchScreenshot.execute({ 'shots' => [] })

    assert_equal false, result[:success]
    assert_match(/no shots/i, result[:error])
  end

  def test_execute_with_single_shot
    params = {
      'shots' => [{ 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'test' }],
      'output_dir' => @test_output_dir,
      'base_name' => 'single'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal true, result[:success]
    assert_equal 1, result[:total_shots]
    assert_equal 1, result[:successful]
    assert_equal 0, result[:failed]
  end

  def test_execute_creates_output_files
    params = {
      'shots' => [{ 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'output_test' }],
      'output_dir' => @test_output_dir,
      'base_name' => 'file'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal true, result[:success]
    expected_file = File.join(@test_output_dir, 'file_output_test.png')
    assert File.exist?(expected_file), "Expected file #{expected_file} to exist"
  end

  # ==========================================================================
  # Camera Type Tests - Standard Views
  # ==========================================================================

  def test_apply_standard_view_top
    camera_spec = { 'type' => 'standard_view', 'view' => 'top' }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    # Top view should look down (negative Z direction)
    camera = @mock_view.camera
    assert_equal false, camera.perspective?
  end

  def test_apply_standard_view_front
    camera_spec = { 'type' => 'standard_view', 'view' => 'front' }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_equal false, camera.perspective?
  end

  def test_apply_standard_view_iso
    camera_spec = { 'type' => 'standard_view', 'view' => 'iso' }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_equal false, camera.perspective?
  end

  def test_apply_standard_view_unknown_raises_error
    camera_spec = { 'type' => 'standard_view', 'view' => 'nonexistent' }

    assert_raises(RuntimeError) do
      SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    end
  end

  # ==========================================================================
  # Camera Type Tests - Custom Camera
  # ==========================================================================

  def test_apply_custom_camera_basic
    camera_spec = {
      'type' => 'custom',
      'eye' => [100, 100, 100],
      'target' => [0, 0, 0]
    }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_in_delta 100.0, camera.eye.x, 0.001
    assert_in_delta 0.0, camera.target.x, 0.001
  end

  def test_apply_custom_camera_with_explicit_up
    camera_spec = {
      'type' => 'custom',
      'eye' => [100, 100, 100],
      'target' => [0, 0, 0],
      'up' => [1, 0, 0]
    }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_in_delta 1.0, camera.up.x, 0.001
    assert_in_delta 0.0, camera.up.y, 0.001
    assert_in_delta 0.0, camera.up.z, 0.001
  end

  def test_apply_custom_camera_with_fov
    camera_spec = {
      'type' => 'custom',
      'eye' => [100, 100, 100],
      'target' => [0, 0, 0],
      'fov' => 60.0
    }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_in_delta 60.0, camera.fov, 0.001
  end

  def test_apply_custom_camera_orthographic
    camera_spec = {
      'type' => 'custom',
      'eye' => [100, 100, 100],
      'target' => [0, 0, 0],
      'perspective' => false
    }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_equal false, camera.perspective?
  end

  # ==========================================================================
  # REGRESSION TESTS - Parallel Vector Bug Fix
  # ==========================================================================

  def test_custom_camera_top_down_view_does_not_raise_parallel_error
    # REGRESNI TEST pro bug BUG-parallel-vector-top-view.md
    # Kamera smeruje primo dolu - eye a target maji stejne X,Y
    camera_spec = {
      'type' => 'custom',
      'eye' => [60, 45, 200],
      'target' => [60, 45, 37.5]
    }

    # Nesmi vyhodit "Up vector cannot be parallel to view direction"
    # Volani bez assert_raises = test projde pokud nevyhodi vyjimku
    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    # Over ze up vector byl nastaven na [0,1,0] misto [0,0,1]
    camera = @mock_view.camera
    assert_in_delta 0.0, camera.up.x, 0.001, 'Up vector X should be 0'
    assert_in_delta 1.0, camera.up.y, 0.001, 'Up vector Y should be 1 for top-down view'
    assert_in_delta 0.0, camera.up.z, 0.001, 'Up vector Z should be 0'
  end

  def test_custom_camera_bottom_up_view_uses_correct_up_vector
    # Pohled zdola nahoru
    camera_spec = {
      'type' => 'custom',
      'eye' => [60, 45, -100],
      'target' => [60, 45, 50]
    }

    # Volani bez assert_raises = test projde pokud nevyhodi vyjimku
    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    # Up vector should be [0, 1, 0] for bottom-up view too
    camera = @mock_view.camera
    assert_in_delta 0.0, camera.up.x, 0.001
    assert_in_delta 1.0, camera.up.y, 0.001
    assert_in_delta 0.0, camera.up.z, 0.001
  end

  def test_custom_camera_explicit_up_vector_is_respected
    # Kdyz uzivatel explicitne zada up vector, pouzij ho
    camera_spec = {
      'type' => 'custom',
      'eye' => [60, 45, 200],
      'target' => [60, 45, 37.5],
      'up' => [1, 0, 0] # Explicitni - i pro top-down view
    }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_in_delta 1.0, camera.up.x, 0.001, 'Explicit up vector should be respected'
    assert_in_delta 0.0, camera.up.y, 0.001
    assert_in_delta 0.0, camera.up.z, 0.001
  end

  def test_custom_camera_diagonal_view_uses_default_up
    # Sikmy pohled - neni paralelni s Z osou, pouzije se default up [0,0,1]
    camera_spec = {
      'type' => 'custom',
      'eye' => [100, 100, 100],
      'target' => [0, 0, 0]
    }

    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)

    camera = @mock_view.camera
    assert_in_delta 0.0, camera.up.x, 0.001
    assert_in_delta 0.0, camera.up.y, 0.001
    assert_in_delta 1.0, camera.up.z, 0.001, 'Default up [0,0,1] should be used for diagonal views'
  end

  # ==========================================================================
  # Camera Type Tests - Zoom Extents Flag
  # ==========================================================================

  def test_zoom_extents_flag_default_is_true
    # Default camera type is now 'standard_view' with zoom_extents: true
    camera_spec = { 'type' => 'standard_view', 'view' => 'iso' }

    # Should not raise - just call it
    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    assert true
  end

  def test_zoom_extents_flag_can_be_disabled
    camera_spec = { 'type' => 'standard_view', 'view' => 'iso', 'zoom_extents' => false }

    # Should not raise - just call it
    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    assert true
  end

  def test_unknown_camera_type_raises_error
    camera_spec = { 'type' => 'invalid_type' }

    error = assert_raises(RuntimeError) do
      SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    end
    assert_match(/Unknown camera type/, error.message)
  end

  def test_apply_zoom_entity_with_valid_id
    # Add entity to model
    entity = Sketchup::Face.new(id: 12_345)
    @mock_model.entities.add_entity(entity)

    camera_spec = {
      'type' => 'zoom_entity',
      'entity_ids' => [12_345]
    }

    # Should not raise - just call it
    SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    assert true
  end

  def test_apply_zoom_entity_invalid_id_raises_error
    camera_spec = {
      'type' => 'zoom_entity',
      'entity_ids' => [99_999]
    }

    assert_raises(RuntimeError) do
      SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    end
  end

  def test_apply_zoom_entity_empty_ids_raises_error
    camera_spec = {
      'type' => 'zoom_entity',
      'entity_ids' => []
    }

    assert_raises(RuntimeError) do
      SupexRuntime::BatchScreenshot.send(:apply_camera, @mock_view, @mock_model, camera_spec)
    end
  end

  # ==========================================================================
  # Batch Processing Tests
  # ==========================================================================

  def test_batch_multiple_shots_success
    params = {
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'shot1' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'shot2' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'shot3' }
      ],
      'output_dir' => @test_output_dir,
      'base_name' => 'batch'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal true, result[:success]
    assert_equal 3, result[:total_shots]
    assert_equal 3, result[:successful]
    assert_equal 0, result[:failed]
  end

  def test_batch_partial_failure_continues
    params = {
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'good1' },
        { 'camera' => { 'type' => 'zoom_entity', 'entity_ids' => [99_999] }, 'name' => 'bad' },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'good2' }
      ],
      'output_dir' => @test_output_dir,
      'base_name' => 'partial'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal false, result[:success] # Overall fails because one shot failed
    assert_equal 3, result[:total_shots]
    assert_equal 2, result[:successful]
    assert_equal 1, result[:failed]
  end

  def test_batch_file_naming_convention
    params = {
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'name' => 'front_view' }
      ],
      'output_dir' => @test_output_dir,
      'base_name' => 'model'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal true, result[:success]
    assert_includes result[:results][0][:file_path], 'model_front_view.png'
  end

  def test_batch_auto_naming_without_shot_name
    params = {
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' } },
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' } }
      ],
      'output_dir' => @test_output_dir,
      'base_name' => 'auto'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal true, result[:success]
    # Should use index-based names: auto_000.png, auto_001.png
    assert_includes result[:results][0][:file_path], 'auto_000.png'
    assert_includes result[:results][1][:file_path], 'auto_001.png'
  end

  # ==========================================================================
  # Error Handling Tests
  # ==========================================================================

  # NOTE: test_unknown_camera_type_raises_error is defined above in Zoom Extents Flag section

  # ==========================================================================
  # Camera State Preservation Tests
  # ==========================================================================

  def test_save_and_restore_camera_state
    # Set initial camera
    original_eye = Geom::Point3d.new(50, 50, 50)
    original_target = Geom::Point3d.new(0, 0, 0)
    original_up = Geom::Vector3d.new(0, 0, 1)
    @mock_view.camera = Sketchup::Camera.new(original_eye, original_target, original_up, true, 45.0)

    # Save state
    state = SupexRuntime::BatchScreenshot.send(:save_camera_state, @mock_view.camera)

    # Modify camera
    @mock_view.camera.eye = Geom::Point3d.new(100, 100, 100)

    # Restore state
    SupexRuntime::BatchScreenshot.send(:restore_camera_state, @mock_view, state)

    # Verify restoration
    assert_in_delta 50.0, @mock_view.camera.eye.x, 0.001
    assert_in_delta 50.0, @mock_view.camera.eye.y, 0.001
    assert_in_delta 50.0, @mock_view.camera.eye.z, 0.001
  end

  # ==========================================================================
  # Isolation Tests (Hide Rest of Model)
  # ==========================================================================

  def test_save_isolation_state
    # Set some isolation state
    @mock_model.active_path = [Sketchup::Group.new]
    @mock_model.rendering_options['InactiveHidden'] = true

    state = SupexRuntime::BatchScreenshot.send(:save_isolation_state, @mock_model)

    assert_equal @mock_model.active_path, state[:active_path]
    assert_equal true, state[:inactive_hidden]
  end

  def test_restore_isolation_state
    # Save original state
    original_active_path = nil
    original_inactive_hidden = false

    # Modify state
    @mock_model.active_path = [Sketchup::Group.new]
    @mock_model.rendering_options['InactiveHidden'] = true

    # Restore
    state = { active_path: original_active_path, inactive_hidden: original_inactive_hidden }
    SupexRuntime::BatchScreenshot.send(:restore_isolation_state, @mock_model, state)

    assert_nil @mock_model.active_path
    assert_equal false, @mock_model.rendering_options['InactiveHidden']
  end

  def test_apply_isolation_with_group
    # Add a group to the model
    group = Sketchup::Group.new(id: 99_999)
    @mock_model.entities.add_entity(group)

    # Apply isolation
    SupexRuntime::BatchScreenshot.send(:apply_isolation, @mock_model, 99_999)

    # Verify active_path was set
    refute_nil @mock_model.active_path
    # Verify InactiveHidden was enabled
    assert_equal true, @mock_model.rendering_options['InactiveHidden']
  end

  def test_apply_isolation_with_component_instance
    # Add a component instance to the model
    component = Sketchup::ComponentInstance.new(id: 88_888)
    @mock_model.entities.add_entity(component)

    # Apply isolation
    SupexRuntime::BatchScreenshot.send(:apply_isolation, @mock_model, 88_888)

    # Verify active_path was set
    refute_nil @mock_model.active_path
    # Verify InactiveHidden was enabled
    assert_equal true, @mock_model.rendering_options['InactiveHidden']
  end

  def test_apply_isolation_with_invalid_entity_raises_error
    # Try to isolate non-existent entity
    assert_raises(RuntimeError) do
      SupexRuntime::BatchScreenshot.send(:apply_isolation, @mock_model, 99_999)
    end
  end

  def test_apply_isolation_with_face_raises_error
    # Add a face (not isolatable)
    face = Sketchup::Face.new(id: 77_777)
    @mock_model.entities.add_entity(face)

    # Should raise error - can only isolate Group/ComponentInstance
    error = assert_raises(RuntimeError) do
      SupexRuntime::BatchScreenshot.send(:apply_isolation, @mock_model, 77_777)
    end
    assert_match(/Can only isolate Group or ComponentInstance/, error.message)
  end

  def test_batch_with_isolation_restores_state
    # Add a group
    group = Sketchup::Group.new(id: 55_555)
    @mock_model.entities.add_entity(group)

    # Verify initial state
    assert_nil @mock_model.active_path
    assert_equal false, @mock_model.rendering_options['InactiveHidden']

    # Execute batch with isolation
    params = {
      'shots' => [
        { 'camera' => { 'type' => 'standard_view', 'view' => 'iso' }, 'isolate' => 55_555, 'name' => 'isolated' }
      ],
      'output_dir' => @test_output_dir,
      'base_name' => 'isolation_test'
    }

    result = SupexRuntime::BatchScreenshot.execute(params)

    assert_equal true, result[:success]
    # Verify state was restored after batch
    assert_nil @mock_model.active_path
    assert_equal false, @mock_model.rendering_options['InactiveHidden']
  end
end
