# frozen_string_literal: true

require_relative 'helpers/test_helper'

class TestUtils < Minitest::Test
  def setup
    SupexRuntime::Utils.clear_console_output
    Sketchup.reset_mocks
  end

  def teardown
    SupexRuntime::Utils.clear_console_output
  end

  # ==========================================================================
  # clean_entity_id tests
  # ==========================================================================

  def test_clean_entity_id_with_integer
    assert_equal 123, SupexRuntime::Utils.clean_entity_id(123)
  end

  def test_clean_entity_id_with_string
    assert_equal 456, SupexRuntime::Utils.clean_entity_id('456')
  end

  def test_clean_entity_id_with_quoted_string
    assert_equal 789, SupexRuntime::Utils.clean_entity_id('"789"')
  end

  def test_clean_entity_id_with_double_quotes
    assert_equal 123, SupexRuntime::Utils.clean_entity_id('""123""')
  end

  # ==========================================================================
  # create_circle_points tests
  # ==========================================================================

  def test_create_circle_points_default_segments
    points = SupexRuntime::Utils.create_circle_points([0, 0, 0], 10)
    assert_equal 24, points.length
  end

  def test_create_circle_points_custom_segments
    points = SupexRuntime::Utils.create_circle_points([0, 0, 0], 10, 12)
    assert_equal 12, points.length
  end

  def test_create_circle_points_preserves_z
    points = SupexRuntime::Utils.create_circle_points([0, 0, 15], 10, 8)
    points.each do |point|
      assert_equal 15, point[2], 'Z coordinate should be preserved'
    end
  end

  def test_create_circle_points_radius_distance
    radius = 5.0
    center = [0, 0, 0]
    points = SupexRuntime::Utils.create_circle_points(center, radius, 8)

    points.each do |point|
      distance = Math.sqrt((point[0] - center[0])**2 + (point[1] - center[1])**2)
      assert_in_delta radius, distance, 0.0001, 'Points should be at radius distance'
    end
  end

  # ==========================================================================
  # create_success_response tests
  # ==========================================================================

  def test_create_success_response_structure
    request = { 'jsonrpc' => '2.0', 'id' => 'test-id' }
    result = { foo: 'bar' }

    response = SupexRuntime::Utils.create_success_response(request, result)

    assert_equal '2.0', response[:jsonrpc]
    assert_equal 'test-id', response[:id]
    assert_equal result, response[:result]
    refute response.key?(:error)
  end

  def test_create_success_response_preserves_id
    request = { 'jsonrpc' => '2.0', 'id' => 'unique-123' }
    response = SupexRuntime::Utils.create_success_response(request, {})

    assert_equal 'unique-123', response[:id]
  end

  def test_create_success_response_defaults_jsonrpc
    request = { 'id' => 1 } # No jsonrpc field
    response = SupexRuntime::Utils.create_success_response(request, {})

    assert_equal '2.0', response[:jsonrpc]
  end

  def test_create_success_response_with_nil_id
    request = { 'jsonrpc' => '2.0', 'id' => nil }
    response = SupexRuntime::Utils.create_success_response(request, { data: 'test' })

    assert_nil response[:id]
    assert_equal({ data: 'test' }, response[:result])
  end

  # ==========================================================================
  # create_error_response tests
  # ==========================================================================

  def test_create_error_response_structure
    request = { 'jsonrpc' => '2.0', 'id' => 'err-id' }
    response = SupexRuntime::Utils.create_error_response(request, 'Something failed')

    assert_equal '2.0', response[:jsonrpc]
    assert_equal 'err-id', response[:id]
    assert response[:error].is_a?(Hash)
    assert_equal 'Something failed', response[:error][:message]
    refute response.key?(:result)
  end

  def test_create_error_response_default_code
    request = { 'jsonrpc' => '2.0', 'id' => 1 }
    response = SupexRuntime::Utils.create_error_response(request, 'Error')

    assert_equal(-32_603, response[:error][:code])
  end

  def test_create_error_response_custom_code
    request = { 'jsonrpc' => '2.0', 'id' => 1 }
    response = SupexRuntime::Utils.create_error_response(request, 'Bad request', -32_600)

    assert_equal(-32_600, response[:error][:code])
  end

  def test_create_error_response_with_data
    request = { 'jsonrpc' => '2.0', 'id' => 1 }
    response = SupexRuntime::Utils.create_error_response(request, 'Error', -32_603, { details: 'extra info' })

    assert_equal({ details: 'extra info', success: false }, response[:error][:data])
  end

  def test_create_error_response_adds_success_false
    request = { 'jsonrpc' => '2.0', 'id' => 1 }
    response = SupexRuntime::Utils.create_error_response(request, 'Error', -32_603, { foo: 'bar' })

    assert_equal false, response[:error][:data][:success]
  end

  def test_create_error_response_preserves_existing_success
    request = { 'jsonrpc' => '2.0', 'id' => 1 }
    response = SupexRuntime::Utils.create_error_response(request, 'Error', -32_603, { success: true })

    # Should preserve explicitly set success value
    assert_equal true, response[:error][:data][:success]
  end

  # ==========================================================================
  # bounds_to_hash tests
  # ==========================================================================

  def test_bounds_to_hash_structure
    bounds = MockBounds.new

    result = SupexRuntime::Utils.bounds_to_hash(bounds)

    assert result.key?(:min)
    assert result.key?(:max)
    assert result.key?(:center)
    assert result[:min].is_a?(Array)
    assert result[:max].is_a?(Array)
    assert result[:center].is_a?(Array)
  end

  def test_bounds_to_hash_values
    min = MockPoint.new(0, 0, 0)
    max = MockPoint.new(10, 20, 30)
    bounds = MockBounds.new(min: min, max: max)

    result = SupexRuntime::Utils.bounds_to_hash(bounds)

    assert_equal [0, 0, 0], result[:min]
    assert_equal [10, 20, 30], result[:max]
    assert_equal [5.0, 10.0, 15.0], result[:center]
  end

  # ==========================================================================
  # console_write tests
  # ==========================================================================

  def test_console_write_captures_message
    SupexRuntime::Utils.console_write('Test message')

    assert_includes SupexRuntime::Utils.console_output, 'Test message'
  end

  def test_console_write_multiple_messages
    SupexRuntime::Utils.console_write('First')
    SupexRuntime::Utils.console_write('Second')

    assert_equal 2, SupexRuntime::Utils.console_output.length
    assert_equal 'First', SupexRuntime::Utils.console_output[0]
    assert_equal 'Second', SupexRuntime::Utils.console_output[1]
  end

  # ==========================================================================
  # show_console tests
  # ==========================================================================

  def test_show_console_calls_sketchup_console
    SKETCHUP_CONSOLE.shown = false

    SupexRuntime::Utils.show_console

    assert SKETCHUP_CONSOLE.shown
  end

  # ==========================================================================
  # find_entity tests
  # ==========================================================================

  def test_find_entity_found
    model = MockModel.new
    entity = Sketchup::Face.new(id: 100)
    model.entities.add_entity(entity)
    Sketchup.mock_model = model

    result = SupexRuntime::Utils.find_entity(100)

    assert_equal entity, result
  end

  def test_find_entity_not_found
    model = MockModel.new
    Sketchup.mock_model = model

    result = SupexRuntime::Utils.find_entity(999)

    assert_nil result
  end

  def test_find_entity_invalid
    model = MockModel.new
    entity = Sketchup::Face.new(id: 100)
    entity.valid = false
    model.entities.add_entity(entity)
    Sketchup.mock_model = model

    result = SupexRuntime::Utils.find_entity(100)

    assert_nil result
  end

  def test_find_entity_with_string_id
    model = MockModel.new
    entity = Sketchup::Edge.new(id: 200)
    model.entities.add_entity(entity)
    Sketchup.mock_model = model

    result = SupexRuntime::Utils.find_entity('200')

    assert_equal entity, result
  end
end
