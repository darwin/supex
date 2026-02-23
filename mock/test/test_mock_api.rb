#!/usr/bin/env ruby
# frozen_string_literal: true

# Self-tests verifying mock API completeness.
# Validates that the SketchUp API mock provides everything needed
# by bridge_server.rb, tools.rb, and vcad_tools.rb.

require 'minitest/autorun'
require 'tmpdir'
require 'fileutils'

# Load the mock SketchUp API
require_relative '../src/sketchup_api/core'

class TestEntityRegistry < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_deterministic_ids
    id1 = SketchupMock::EntityRegistry.next_id
    id2 = SketchupMock::EntityRegistry.next_id
    assert_equal 1, id1
    assert_equal 2, id2
  end

  def test_register_and_find
    defn = Sketchup::ComponentDefinition.new('test')
    found = SketchupMock::EntityRegistry.find(defn.entityID)
    assert_equal defn, found
  end

  def test_reset
    _defn = Sketchup::ComponentDefinition.new('test')
    SketchupMock::EntityRegistry.reset
    assert_equal 1, SketchupMock::EntityRegistry.next_id
    assert_nil SketchupMock::EntityRegistry.find(1)
  end
end

class TestGeometry < Minitest::Test
  def test_point3d_construction
    p = Geom::Point3d.new(1.0, 2.0, 3.0)
    assert_equal 1.0, p.x
    assert_equal 2.0, p.y
    assert_equal 3.0, p.z
  end

  def test_point3d_from_array
    p = Geom::Point3d.new([4.0, 5.0, 6.0])
    assert_equal [4.0, 5.0, 6.0], p.to_a
  end

  def test_point3d_default
    p = Geom::Point3d.new
    assert_equal [0.0, 0.0, 0.0], p.to_a
  end

  def test_point3d_vector_to
    p1 = Geom::Point3d.new(0, 0, 0)
    p2 = Geom::Point3d.new(3, 4, 0)
    v = p1.vector_to(p2)
    assert_equal 3.0, v.x
    assert_equal 4.0, v.y
    assert_in_delta 5.0, v.length, 0.0001
  end

  def test_point3d_distance
    p1 = Geom::Point3d.new(0, 0, 0)
    p2 = Geom::Point3d.new(3, 4, 0)
    assert_in_delta 5.0, p1.distance(p2), 0.0001
  end

  def test_vector3d_normalize
    v = Geom::Vector3d.new(3, 0, 0)
    n = v.normalize
    assert_in_delta 1.0, n.x, 0.0001
    assert_in_delta 0.0, n.y, 0.0001
    # Original unchanged
    assert_equal 3.0, v.x
  end

  def test_vector3d_reverse
    v = Geom::Vector3d.new(1, 2, 3)
    r = v.reverse
    assert_equal(-1.0, r.x)
    assert_equal(-2.0, r.y)
    assert_equal(-3.0, r.z)
  end

  def test_vector3d_parallel
    v1 = Geom::Vector3d.new(1, 0, 0)
    v2 = Geom::Vector3d.new(2, 0, 0)
    v3 = Geom::Vector3d.new(0, 1, 0)
    assert v1.parallel?(v2)
    refute v1.parallel?(v3)
  end

  def test_bounding_box
    bb = Geom::BoundingBox.new
    assert bb.empty?

    bb.add(Geom::Point3d.new(0, 0, 0))
    bb.add(Geom::Point3d.new(10, 20, 30))
    refute bb.empty?

    assert_equal 0.0, bb.min.x
    assert_equal 10.0, bb.max.x
    assert_equal 5.0, bb.center.x
    assert_equal 10.0, bb.center.y
  end
end

class TestTransformation < Minitest::Test
  def test_from_point
    pt = Geom::Point3d.new(10, 20, 30)
    tr = Geom::Transformation.new(pt)
    assert_equal 10.0, tr.origin.x
    assert_equal 20.0, tr.origin.y
    assert_equal 30.0, tr.origin.z
  end

  def test_to_a
    tr = Geom::Transformation.new
    a = tr.to_a
    assert_equal 16, a.length
    assert_equal 1.0, a[0] # identity diagonal
    assert_equal 1.0, a[5]
    assert_equal 1.0, a[10]
    assert_equal 1.0, a[15]
  end

  def test_from_array
    arr = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 10, 15, 1]
    tr = Geom::Transformation.new(arr)
    assert_equal 5.0, tr.origin.x
    assert_equal 10.0, tr.origin.y
    assert_equal 15.0, tr.origin.z
  end
end

class TestUnits < Minitest::Test
  def test_mm_to_inches
    assert_in_delta 1.0, 25.4.mm, 0.0001
  end

  def test_inches_to_mm
    assert_in_delta 25.4, 1.0.to_mm, 0.0001
  end

  def test_roundtrip
    original = 100.0
    assert_in_delta original, original.mm.to_mm, 0.0001
  end
end

class TestAttributeDictionary < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_set_and_get
    defn = Sketchup::ComponentDefinition.new('test')
    defn.set_attribute('vcad', 'node_id', 'node-1')
    assert_equal 'node-1', defn.get_attribute('vcad', 'node_id')
  end

  def test_get_with_default
    defn = Sketchup::ComponentDefinition.new('test')
    assert_equal 42, defn.get_attribute('vcad', 'missing', 42)
  end

  def test_get_nil_without_default
    defn = Sketchup::ComponentDefinition.new('test')
    assert_nil defn.get_attribute('vcad', 'missing')
  end

  def test_multiple_dicts
    defn = Sketchup::ComponentDefinition.new('test')
    defn.set_attribute('vcad', 'node_id', 'n1')
    defn.set_attribute('other', 'key', 'val')
    assert_equal 'n1', defn.get_attribute('vcad', 'node_id')
    assert_equal 'val', defn.get_attribute('other', 'key')
  end
end

class TestComponentDefinition < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_creation
    defn = Sketchup::ComponentDefinition.new('MyComponent')
    assert_equal 'MyComponent', defn.name
    assert_kind_of Integer, defn.entityID
    assert defn.valid?
  end

  def test_is_a_check
    defn = Sketchup::ComponentDefinition.new('test')
    assert defn.is_a?(Sketchup::ComponentDefinition)
    assert defn.is_a?(Sketchup::Entity)
  end

  def test_instances_tracking
    defn = Sketchup::ComponentDefinition.new('test')
    assert_empty defn.instances
  end

  def test_typename
    defn = Sketchup::ComponentDefinition.new('test')
    assert_equal 'ComponentDefinition', defn.typename
  end

  def test_bounds
    defn = Sketchup::ComponentDefinition.new('test')
    assert_kind_of Geom::BoundingBox, defn.bounds
  end

  def test_entities
    defn = Sketchup::ComponentDefinition.new('test')
    assert_kind_of SketchupMock::MockEntities, defn.entities
  end
end

class TestComponentInstance < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_creation
    defn = Sketchup::ComponentDefinition.new('comp')
    inst = Sketchup::ComponentInstance.new(defn)
    assert_equal defn, inst.definition
    assert inst.valid?
    assert_equal '', inst.name
  end

  def test_typename
    defn = Sketchup::ComponentDefinition.new('comp')
    inst = Sketchup::ComponentInstance.new(defn)
    assert_equal 'ComponentInstance', inst.typename
  end

  def test_transformation
    defn = Sketchup::ComponentDefinition.new('comp')
    pt = Geom::Point3d.new(10, 20, 30)
    tr = Geom::Transformation.new(pt)
    inst = Sketchup::ComponentInstance.new(defn, tr)
    assert_equal 10.0, inst.transformation.origin.x
  end

  def test_erase
    defn = Sketchup::ComponentDefinition.new('comp')
    entities = SketchupMock::MockEntities.new
    inst = entities.add_instance(defn)
    assert_equal 1, defn.instances.length
    assert_equal 1, entities.count

    inst.erase!
    refute inst.valid?
    assert_equal 0, defn.instances.length
  end

  def test_respond_to
    defn = Sketchup::ComponentDefinition.new('comp')
    inst = Sketchup::ComponentInstance.new(defn)
    assert inst.respond_to?(:layer)
    assert inst.respond_to?(:material)
    assert inst.respond_to?(:name)
    assert inst.respond_to?(:name=)
    assert inst.respond_to?(:bounds)
  end
end

class TestEntities < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_add_instance
    entities = SketchupMock::MockEntities.new
    defn = Sketchup::ComponentDefinition.new('comp')
    inst = entities.add_instance(defn)

    assert_kind_of Sketchup::ComponentInstance, inst
    assert_equal defn, inst.definition
    assert_equal 1, entities.count
    assert_equal 1, defn.instances.length
  end

  def test_add_instance_with_transformation
    entities = SketchupMock::MockEntities.new
    defn = Sketchup::ComponentDefinition.new('comp')
    tr = Geom::Transformation.new(Geom::Point3d.new(1, 2, 3))
    inst = entities.add_instance(defn, tr)

    assert_equal 1.0, inst.transformation.origin.x
  end

  def test_parent_chain
    entities = SketchupMock::MockEntities.new
    defn = Sketchup::ComponentDefinition.new('comp')
    inst = entities.add_instance(defn)

    # inst.parent.entities should return the same entities collection
    assert_equal entities, inst.parent.entities
  end

  def test_grep
    entities = SketchupMock::MockEntities.new
    defn = Sketchup::ComponentDefinition.new('comp')
    entities.add_instance(defn)
    entities.add_face

    assert_equal 1, entities.grep(Sketchup::ComponentInstance).length
    assert_equal 1, entities.grep(Sketchup::Face).length
    assert_equal 2, entities.count
  end

  def test_clear_bang
    entities = SketchupMock::MockEntities.new
    defn = Sketchup::ComponentDefinition.new('comp')
    inst = entities.add_instance(defn)

    entities.clear!
    assert_equal 0, entities.count
    refute inst.valid?
  end

  def test_manifold
    entities = SketchupMock::MockEntities.new
    assert entities.manifold?
    entities.set_manifold(false)
    refute entities.manifold?
  end
end

class TestDefinitionList < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
    @tmpdir = Dir.mktmpdir
  end

  def teardown
    FileUtils.rm_rf(@tmpdir)
  end

  def test_import_obj
    mesh_path = File.join(@tmpdir, 'test.obj')
    File.write(mesh_path, <<~OBJ)
      v 0.0 0.0 0.0
      v 10.0 0.0 0.0
      v 10.0 10.0 0.0
      v 0.0 10.0 0.0
      f 1 2 3
      f 1 3 4
    OBJ

    defs = SketchupMock::MockDefinitionList.new
    defn = defs.import(mesh_path)

    assert_kind_of Sketchup::ComponentDefinition, defn
    assert defn.is_a?(Sketchup::ComponentDefinition)
    refute defn.bounds.empty?
    assert_in_delta 0.0, defn.bounds.min.x, 0.0001
    assert_in_delta 10.0, defn.bounds.max.x, 0.0001
    assert_in_delta 10.0, defn.bounds.max.y, 0.0001
  end

  def test_import_nonexistent_raises
    defs = SketchupMock::MockDefinitionList.new
    assert_raises(RuntimeError) { defs.import('/nonexistent/file.obj') }
  end

  def test_enumerable
    defs = SketchupMock::MockDefinitionList.new
    defs.add('def1')
    defs.add('def2')

    names = defs.map(&:name)
    assert_includes names, 'def1'
    assert_includes names, 'def2'
  end

  def test_select_and_find
    defs = SketchupMock::MockDefinitionList.new
    defs.add('alpha')
    defs.add('beta')

    found = defs.find { |d| d.name == 'beta' }
    assert_equal 'beta', found.name

    selected = defs.select { |d| d.name.start_with?('a') }
    assert_equal 1, selected.length
  end

  def test_remove
    defs = SketchupMock::MockDefinitionList.new
    defn = defs.add('removeme')
    assert_equal 1, defs.count

    defs.remove(defn)
    assert_equal 0, defs.count
  end
end

class TestModel < Minitest::Test
  def setup
    Sketchup.reset_mocks
  end

  def test_active_model
    model = Sketchup.active_model
    assert_kind_of SketchupMock::MockModel, model
  end

  def test_model_title
    model = Sketchup.active_model
    assert_equal 'Untitled', model.title
  end

  def test_model_entities
    model = Sketchup.active_model
    assert_kind_of SketchupMock::MockEntities, model.entities
    assert_equal model.entities, model.active_entities
  end

  def test_model_definitions
    model = Sketchup.active_model
    assert_kind_of SketchupMock::MockDefinitionList, model.definitions
  end

  def test_model_operations
    model = Sketchup.active_model
    assert model.start_operation('test', true)
    assert model.commit_operation
  end

  def test_model_options
    model = Sketchup.active_model
    assert_equal 2, model.options['UnitsOptions']['LengthUnit']
  end

  def test_find_entity_by_id
    model = Sketchup.active_model
    defn = Sketchup::ComponentDefinition.new('findme')
    found = model.find_entity_by_id(defn.entityID)
    assert_equal defn, found
  end

  def test_model_reset
    model = Sketchup.active_model
    model.definitions.add('test')
    assert_equal 1, model.definitions.count

    model.reset
    assert_equal 0, model.definitions.count
    assert_equal 0, model.entities.count
  end

  def test_sketchup_version
    assert_equal '2026.0.0', Sketchup.version
  end

  def test_sketchup_reset_mocks
    model = Sketchup.active_model
    _defn = Sketchup::ComponentDefinition.new('test')
    Sketchup.reset_mocks
    new_model = Sketchup.active_model
    refute_equal model.object_id, new_model.object_id
  end
end

class TestFace < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_face_creation
    face = Sketchup::Face.new
    assert_equal 100.0, face.area
    assert_equal 'Face', face.typename
    assert face.valid?
  end

  def test_face_mesh
    face = Sketchup::Face.new
    mesh = face.mesh
    assert_kind_of SketchupMock::MockPolygonMesh, mesh
    assert_equal 3, mesh.count_points
    assert_equal 1, mesh.count_polygons
  end
end

class TestEdge < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_edge_creation
    edge = Sketchup::Edge.new
    assert_equal 10.0, edge.length
    assert_equal 'Edge', edge.typename
  end
end

class TestPolygonMesh < Minitest::Test
  def test_one_based_indexing
    mesh = SketchupMock::MockPolygonMesh.new
    idx1 = mesh.add_point(Geom::Point3d.new(0, 0, 0))
    idx2 = mesh.add_point(Geom::Point3d.new(1, 0, 0))
    idx3 = mesh.add_point(Geom::Point3d.new(1, 1, 0))
    mesh.add_polygon(idx1, idx2, idx3)

    assert_equal 1, idx1
    assert_equal 2, idx2
    assert_equal 3, idx3

    pt = mesh.point_at(1)
    assert_equal 0.0, pt.x

    pt2 = mesh.point_at(2)
    assert_equal 1.0, pt2.x

    poly = mesh.polygon_at(1)
    assert_equal [1, 2, 3], poly
  end
end

class TestUI < Minitest::Test
  def setup
    UI.reset_ui_mocks
  end

  def test_start_stop_timer
    id = UI.start_timer(0.1, true) { 'tick' }
    assert_kind_of Integer, id
    assert UI.timers.key?(id)

    UI.stop_timer(id)
    refute UI.timers.key?(id)
  end

  def test_blocking_mode
    refute UI.blocking_mode?
    UI.enable_blocking_mode!
    assert UI.blocking_mode?
  end

  def test_blocking_mode_captures_timer
    UI.enable_blocking_mode!
    captured = false
    UI.start_timer(0.01, true) { captured = true }

    # Verify that run_blocking_loop! would work (don't actually run it - it blocks)
    # Instead, verify the timer was captured by checking the internal state
    refute_nil UI.instance_variable_get(:@blocking_timer)
  end

  def test_messagebox
    result = UI.messagebox('test message', MB_OK)
    assert_equal 1, result
    assert_equal 1, UI.messageboxes.length
    assert_equal 'test message', UI.messageboxes.first[:message]
  end

  def test_menu
    menu = UI.menu('Extensions')
    assert_kind_of MockMenu, menu
    menu.add_item('Test') {}
    assert_equal 1, menu.items.length
  end
end

class TestSketchupConsole < Minitest::Test
  def test_console_show
    SKETCHUP_CONSOLE.show
    assert SKETCHUP_CONSOLE.shown
  end
end

class TestCamera < Minitest::Test
  def test_camera_defaults
    cam = SketchupMock::MockCamera.new
    assert cam.perspective?
    assert_equal 45.0, cam.fov
    assert_kind_of Geom::Point3d, cam.eye
  end

  def test_view
    view = SketchupMock::MockView.new
    assert_kind_of SketchupMock::MockCamera, view.camera
  end

  def test_view_write_image
    Dir.mktmpdir do |tmpdir|
      path = File.join(tmpdir, 'test.png')
      view = SketchupMock::MockView.new
      view.write_image(filename: path)
      assert File.exist?(path)
    end
  end
end

class TestSelection < Minitest::Test
  def setup
    SketchupMock::EntityRegistry.reset
  end

  def test_add_and_count
    sel = SketchupMock::MockSelection.new
    face = Sketchup::Face.new
    sel.add(face)
    assert_equal 1, sel.count
  end

  def test_clear
    sel = SketchupMock::MockSelection.new
    sel.add(Sketchup::Face.new)
    sel.clear
    assert_equal 0, sel.count
  end
end

class TestLayers < Minitest::Test
  def test_default_layer
    layers = SketchupMock::MockLayers.new
    assert_equal 1, layers.count
    assert_equal 'Layer0', layers.first.name
  end

  def test_add_layer
    layers = SketchupMock::MockLayers.new
    layers.add('Custom')
    assert_equal 2, layers.count
  end

  def test_layer_visible
    layer = SketchupMock::MockLayer.new
    assert layer.visible?
  end
end

class TestMaterials < Minitest::Test
  def test_empty_by_default
    mats = SketchupMock::MockMaterials.new
    assert_equal 0, mats.count
  end

  def test_add_material
    mats = SketchupMock::MockMaterials.new
    mat = mats.add('Steel')
    assert_equal 'Steel', mat.name
    assert_equal 1, mats.count
  end

  def test_material_color
    mat = SketchupMock::MockMaterial.new(name: 'Red')
    assert_kind_of SketchupMock::MockColor, mat.color
    assert_equal 255, mat.color.red
  end
end

class TestTestControl < Minitest::Test
  def setup
    Sketchup.reset_mocks
    # Load test control module for direct testing
    require_relative '../src/test_control'
    @ctrl = Object.new
    @ctrl.extend(SketchupMock::TestControl)
  end

  def test_reset
    model = Sketchup.active_model
    model.definitions.add('before_reset')
    result = @ctrl.send(:execute_test_tool, '_test.reset', nil)
    assert result[:success]
    # After reset, fresh model
    assert_equal 0, Sketchup.active_model.definitions.count
  end

  def test_add_definition
    result = @ctrl.send(:execute_test_tool, '_test.add_definition', {
                          'name' => 'test_def',
                          'attributes' => { 'vcad' => { 'node_id' => 'n1' } }
                        })
    assert result[:success]
    assert_equal 'test_def', result[:name]

    defn = Sketchup.active_model.definitions.find { |d| d.name == 'test_def' }
    assert_equal 'n1', defn.get_attribute('vcad', 'node_id')
  end

  def test_add_instance
    @ctrl.send(:execute_test_tool, '_test.add_definition', { 'name' => 'comp' })
    result = @ctrl.send(:execute_test_tool, '_test.add_instance', {
                          'definition_name' => 'comp',
                          'position' => [10, 20, 30]
                        })
    assert result[:success]
    assert_equal 'comp', result[:definition_name]
  end

  def test_add_entity_face
    result = @ctrl.send(:execute_test_tool, '_test.add_entity', {
                          'type' => 'face',
                          'area' => 50.0
                        })
    assert result[:success]
    assert_equal 'Face', result[:type]
  end

  def test_set_and_get_attribute
    result = @ctrl.send(:execute_test_tool, '_test.add_definition', { 'name' => 'attr_test' })
    entity_id = result[:entity_id]

    @ctrl.send(:execute_test_tool, '_test.set_attribute', {
                 'entity_id' => entity_id,
                 'dict' => 'custom',
                 'key' => 'foo',
                 'value' => 'bar'
               })

    get_result = @ctrl.send(:execute_test_tool, '_test.get_entity', {
                              'entity_id' => entity_id
                            })
    assert get_result[:success]
    assert_equal 'bar', get_result[:attributes]['custom']['foo']
  end

  def test_set_manifold
    result = @ctrl.send(:execute_test_tool, '_test.set_manifold', { 'value' => false })
    assert result[:success]
    refute Sketchup.active_model.active_entities.manifold?
  end

  def test_get_state
    @ctrl.send(:execute_test_tool, '_test.add_definition', { 'name' => 'state_test' })
    result = @ctrl.send(:execute_test_tool, '_test.get_state', nil)
    assert result[:success]
    assert_equal 1, result[:definition_count]
  end
end

class TestVCADToolsIntegration < Minitest::Test
  # Integration test: verify the mock API surface supports vcad_tools.rb operations

  def setup
    Sketchup.reset_mocks
    @tmpdir = Dir.mktmpdir
  end

  def teardown
    FileUtils.rm_rf(@tmpdir)
  end

  def test_vcad_place_node_workflow
    # Simulate what vcad_tools.rb#place_vcad_node does
    model = Sketchup.active_model

    # Create test mesh file
    mesh_path = File.join(@tmpdir, 'cube.obj')
    File.write(mesh_path, <<~OBJ)
      v 0.0 0.0 0.0
      v 1.0 0.0 0.0
      v 1.0 1.0 0.0
      v 0.0 1.0 0.0
      v 0.0 0.0 1.0
      v 1.0 0.0 1.0
      v 1.0 1.0 1.0
      v 0.0 1.0 1.0
      f 1 2 3 4
      f 5 6 7 8
      f 1 2 6 5
      f 2 3 7 6
      f 3 4 8 7
      f 4 1 5 8
    OBJ

    model.start_operation('Place vcad node', true)

    defn = model.definitions.import(mesh_path)
    assert defn.is_a?(Sketchup::ComponentDefinition)

    defn.name = 'vcad_node-1'
    defn.set_attribute('vcad', 'node_id', 'node-1')
    defn.set_attribute('vcad', 'source_file', '/path/to/source.skp.oo')
    defn.set_attribute('vcad', 'version', 1)

    pt = Geom::Point3d.new(100.0.mm, 200.0.mm, 0.0.mm)
    tr = Geom::Transformation.new(pt)
    instance = model.active_entities.add_instance(defn, tr)

    model.commit_operation

    # Verify
    assert instance.valid?
    assert_equal 'vcad_node-1', defn.name
    assert_equal 'node-1', defn.get_attribute('vcad', 'node_id')
    assert_equal 1, defn.instances.length
    assert_in_delta 100.0 / 25.4, instance.transformation.origin.x, 0.0001
  end

  def test_vcad_update_node_workflow
    # Simulate what vcad_tools.rb#update_vcad_node does
    model = Sketchup.active_model

    mesh_path = File.join(@tmpdir, 'v1.obj')
    File.write(mesh_path, "v 0 0 0\nv 1 0 0\nv 1 1 0\nf 1 2 3\n")

    # Place initial node
    model.start_operation('Place', true)
    old_defn = model.definitions.import(mesh_path)
    old_defn.name = 'bracket'
    old_defn.set_attribute('vcad', 'node_id', 'b1')
    old_defn.set_attribute('vcad', 'version', 1)
    tr = Geom::Transformation.new(Geom::Point3d.new(5, 0, 0))
    inst = model.active_entities.add_instance(old_defn, tr)
    model.commit_operation

    # Update: atomic definition swap
    mesh_v2 = File.join(@tmpdir, 'v2.obj')
    File.write(mesh_v2, "v 0 0 0\nv 2 0 0\nv 2 2 0\nf 1 2 3\n")

    model.start_operation('Update vcad node', true)

    placements = old_defn.instances.map do |i|
      {
        parent_entities: i.parent.entities,
        transformation: i.transformation,
        layer: i.respond_to?(:layer) ? i.layer : nil,
        material: i.respond_to?(:material) ? i.material : nil,
        name: i.respond_to?(:name) ? i.name : nil
      }
    end

    new_defn = model.definitions.import(mesh_v2)
    new_defn.name = 'bracket__updating'
    new_defn.set_attribute('vcad', 'node_id', 'b1')
    new_defn.set_attribute('vcad', 'version', 2)

    old_instances = old_defn.instances.to_a
    placements.each_with_index do |placement, idx|
      replacement = placement[:parent_entities].add_instance(new_defn, placement[:transformation])
      replacement.layer = placement[:layer] if placement[:layer]
      replacement.material = placement[:material] if placement[:material]
      old_instances[idx]&.erase!
    end

    old_defn.name = 'bracket__old'
    new_defn.name = 'bracket'
    model.definitions.remove(old_defn) if old_defn.instances.empty?

    model.commit_operation

    # Verify
    assert_equal 'bracket', new_defn.name
    assert_equal 2, new_defn.get_attribute('vcad', 'version')
    assert_equal 1, new_defn.instances.length

    # Old instance erased
    refute inst.valid?

    # New instance at same position
    new_inst = new_defn.instances.first
    assert_equal 5.0, new_inst.transformation.origin.x
  end

  def test_vcad_list_nodes_workflow
    model = Sketchup.active_model

    d1 = model.definitions.add('bracket')
    d1.set_attribute('vcad', 'node_id', 'n1')

    d2 = model.definitions.add('plate')
    d2.set_attribute('vcad', 'node_id', 'n2')

    model.definitions.add('not-vcad')

    vcad_defs = model.definitions.select { |d| d.get_attribute('vcad', 'node_id') }
    assert_equal 2, vcad_defs.length

    node_ids = vcad_defs.map { |d| d.get_attribute('vcad', 'node_id') }
    assert_includes node_ids, 'n1'
    assert_includes node_ids, 'n2'
  end

  def test_vcad_bounds_in_mm
    model = Sketchup.active_model

    mesh_path = File.join(@tmpdir, 'box.obj')
    File.write(mesh_path, <<~OBJ)
      v 0.0 0.0 0.0
      v 2.0 0.0 0.0
      v 2.0 3.0 0.0
      v 0.0 3.0 0.0
      f 1 2 3 4
    OBJ

    defn = model.definitions.import(mesh_path)
    bb = defn.bounds

    # bounds in internal units, .to_mm converts
    assert_in_delta 0.0, bb.min.x.to_mm, 0.0001
    assert_in_delta 2.0 * 25.4, bb.max.x.to_mm, 0.0001
  end
end

class TestRealRuntimeLoading < Minitest::Test
  # Verify that the real supex runtime code can be loaded with the mock

  def setup
    Sketchup.reset_mocks
    runtime_src = File.expand_path('../../runtime/src/supex_runtime', __dir__)
    require File.join(runtime_src, 'bridge_server')
  end

  def test_load_bridge_server
    assert defined?(SupexRuntime::BridgeServer)
    assert defined?(SupexRuntime::Tools)
    assert defined?(SupexRuntime::VCADTools)
    assert defined?(SupexRuntime::VERSION)
  end

  def test_bridge_server_instantiation
    server = SupexRuntime::BridgeServer.new(port: 0)
    assert_kind_of SupexRuntime::BridgeServer, server
  end
end
