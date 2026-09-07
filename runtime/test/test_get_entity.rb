# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/bridge_server'

class TestGetEntity < Minitest::Test
  def setup
    Sketchup.reset_mocks
    @model = Sketchup.active_model
    @server = SupexRuntime::BridgeServer.new
  end

  def teardown
    Sketchup.reset_mocks
  end

  def test_group_details
    group = Sketchup::Group.new(id: 42, name: 'Table')
    group.bounds = MockBounds.new(min: MockPoint.new(1, 2, 3), max: MockPoint.new(11, 22, 33))
    group.transformation = Geom::Transformation.new(Geom::Point3d.new(5, 6, 7))
    group.material = MockMaterial.new(name: 'Wood')
    group.locked = true
    @model.entities.add_entity(group)

    result = @server.send(:execute_tool, 'get_entity', { 'entity_id' => 42 })

    assert result[:success]
    assert_equal 'Group', result[:type]
    assert_equal 42, result[:entity_id]
    assert_equal 'Table', result[:name]
    assert_equal 'Layer0', result[:layer]
    assert_equal 'Wood', result[:material]
    assert_equal true, result[:locked]
    assert_equal false, result[:hidden]
    assert_equal true, result[:visible]
    assert_equal [1.0, 2.0, 3.0], result[:bounds][:min]
    assert_equal [11.0, 22.0, 33.0], result[:bounds][:max]
    assert_equal({ width: 10.0, depth: 20.0, height: 30.0 }, result[:dimensions])
    assert_equal 16, result[:transformation].length
    assert_equal [5.0, 6.0, 7.0], result[:origin]
  end

  def test_component_instance_details
    definition = MockComponentDefinition.new('Leg')
    instance = @model.entities.add_instance(definition, Geom::Transformation.new)
    instance.entityID = 7
    instance.name = 'Leg 1'

    result = @server.send(:execute_tool, 'get_entity', { 'entity_id' => 7 })

    assert result[:success]
    assert_equal 'ComponentInstance', result[:type]
    assert_equal 'Leg', result[:name]
    assert_equal 'Leg', result[:definition]
    assert_equal 'Leg 1', result[:instance_name]
    assert_equal [0.0, 0.0, 0.0], result[:origin]
  end

  def test_face_details_without_instance_data
    face = Sketchup::Face.new(id: 9, area: 12.5)
    @model.entities.add_entity(face)

    result = @server.send(:execute_tool, 'get_entity', { 'entity_id' => '9' })

    assert result[:success]
    assert_equal 'Face', result[:type]
    assert_in_delta 12.5, result[:area]
    assert result.key?(:bounds)
    refute result.key?(:transformation)
  end

  def test_unknown_entity
    result = @server.send(:execute_tool, 'get_entity', { 'entity_id' => 12_345 })

    assert_equal false, result[:success]
    assert_match(/not found/i, result[:error])
  end

  def test_missing_entity_id
    result = @server.send(:execute_tool, 'get_entity', {})

    assert_equal false, result[:success]
    assert_match(/entity_id/, result[:error])
  end

  def test_no_active_model
    Sketchup.force_no_model = true

    result = @server.send(:execute_tool, 'get_entity', { 'entity_id' => 1 })

    assert_equal false, result[:success]
    assert_match(/no active model/i, result[:error])
  end
end
