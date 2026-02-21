# frozen_string_literal: true

# Test control API for su-mock.
# Dispatches _test.* tool calls for Python test setup/teardown.
# Patched into BridgeServer#execute_tool via prepend.

module SketchupMock
  module TestControl
    # Intercept _test.* tools before normal dispatch
    def execute_tool(tool_name, args, workspace = nil)
      if tool_name.start_with?('_test.')
        execute_test_tool(tool_name, args)
      else
        super
      end
    end

    private

    def execute_test_tool(tool_name, args)
      case tool_name
      when '_test.reset'
        test_reset
      when '_test.add_definition'
        test_add_definition(args || {})
      when '_test.add_instance'
        test_add_instance(args || {})
      when '_test.add_entity'
        test_add_entity(args || {})
      when '_test.set_attribute'
        test_set_attribute(args || {})
      when '_test.get_entity'
        test_get_entity(args || {})
      when '_test.set_manifold'
        test_set_manifold(args || {})
      when '_test.get_state'
        test_get_state
      else
        raise "Unknown test tool: #{tool_name}"
      end
    end

    # Reset all model state to clean
    def test_reset
      Sketchup.reset_mocks
      # Force fresh model creation
      _model = Sketchup.active_model
      { success: true, message: 'Model state reset' }
    end

    # Create ComponentDefinition with attributes
    def test_add_definition(args)
      model = Sketchup.active_model
      name = args['name'] || "test_def_#{model.definitions.count}"
      defn = model.definitions.add(name)

      # Set optional attributes
      (args['attributes'] || {}).each do |dict, entries|
        entries.each { |key, value| defn.set_attribute(dict, key, value) }
      end

      {
        success: true,
        entity_id: defn.entityID,
        name: defn.name
      }
    end

    # Place instance of a definition
    def test_add_instance(args)
      model = Sketchup.active_model
      defn_name = args['definition_name']
      position = args['position'] || [0, 0, 0]

      defn = model.definitions.find { |d| d.name == defn_name }
      raise "Definition not found: #{defn_name}" unless defn

      pt = Geom::Point3d.new(position[0].to_f, position[1].to_f, position[2].to_f)
      tr = Geom::Transformation.new(pt)
      instance = model.active_entities.add_instance(defn, tr)
      instance.name = args['name'] if args['name']

      {
        success: true,
        entity_id: instance.entityID,
        definition_name: defn.name
      }
    end

    # Add entity (Face, Edge, Group) with properties
    def test_add_entity(args)
      model = Sketchup.active_model
      type = args['type'] || 'face'

      entity = case type.downcase
               when 'face'
                 face = model.active_entities.add_face
                 face.area = args['area'].to_f if args['area']
                 face
               when 'edge'
                 edge = model.active_entities.add_edge
                 edge.length = args['length'].to_f if args['length']
                 edge
               when 'group'
                 group = model.active_entities.add_group
                 group.name = args['name'] if args['name']
                 group
               else
                 raise "Unknown entity type: #{type}"
               end

      {
        success: true,
        entity_id: entity.entityID,
        type: entity.typename
      }
    end

    # Set attribute dict entry on entity by ID
    def test_set_attribute(args)
      entity_id = args['entity_id'].to_i
      dict = args['dict'] || args['dictionary']
      key = args['key']
      value = args['value']

      entity = SketchupMock::EntityRegistry.find(entity_id)
      raise "Entity not found: #{entity_id}" unless entity

      entity.set_attribute(dict, key, value)

      { success: true, entity_id: entity_id }
    end

    # Return entity state by ID (for assertions)
    def test_get_entity(args)
      entity_id = args['entity_id'].to_i
      entity = SketchupMock::EntityRegistry.find(entity_id)
      raise "Entity not found: #{entity_id}" unless entity

      data = {
        success: true,
        entity_id: entity.entityID,
        type: entity.typename,
        valid: entity.valid?
      }

      # Type-specific fields
      case entity
      when Sketchup::ComponentDefinition
        data[:name] = entity.name
        data[:instances_count] = entity.instances.length
        data[:attributes] = entity.attribute_dictionaries
      when Sketchup::ComponentInstance
        data[:name] = entity.name
        data[:definition_name] = entity.definition.name
        data[:attributes] = entity.attribute_dictionaries
      when Sketchup::Face
        data[:area] = entity.area
      when Sketchup::Edge
        data[:length] = entity.length
      when Sketchup::Group
        data[:name] = entity.name
      end

      data
    end

    # Configure manifold? return value on model entities
    def test_set_manifold(args)
      model = Sketchup.active_model
      value = [true, 'true'].include?(args['value'])
      model.active_entities.set_manifold(value)

      { success: true, manifold: value }
    end

    # Full model state snapshot
    def test_get_state
      model = Sketchup.active_model
      {
        success: true,
        title: model.title,
        entity_count: model.entities.count,
        definition_count: model.definitions.count,
        entities: model.entities.map { |e| { id: e.entityID, type: e.typename } },
        definitions: model.definitions.map { |d| { id: d.entityID, name: d.name } }
      }
    end
  end
end
