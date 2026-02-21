# frozen_string_literal: true

require_relative 'path_policy'

module SupexRuntime
  # Tool implementations for vcad node management in SketchUp.
  # Handles mesh import, vcad attribute storage, and instance lifecycle.
  module VCADTools
    extend self

    VCAD_DICT = 'vcad'

    # Import OBJ as ComponentDefinition, set vcad attributes, place instance
    # @param params [Hash] parameters: obj_path, node_id, source_file, component_name, position
    # @param workspace [String, nil] workspace path for path validation
    # @return [Hash] result with entity_id, definition_name
    def place_vcad_node(params, workspace: nil)
      obj_path = params['obj_path']
      node_id = params['node_id']
      source_file = params['source_file']
      component_name = params['component_name'] || "vcad_#{node_id}"
      position = params['position'] || [0, 0, 0]

      PathPolicy.validate!(obj_path, operation: 'vcad import', workspace: workspace)
      PathPolicy.validate!(source_file, operation: 'vcad source', workspace: workspace) if source_file

      model = Sketchup.active_model
      model.start_operation('Place vcad node', true)

      # SketchUp 2026: definitions.import returns ComponentDefinition.
      defn = model.definitions.import(obj_path)
      unless defn.is_a?(Sketchup::ComponentDefinition)
        raise "IMPORT_DEFINITION_NOT_FOUND: #{obj_path}"
      end
      defn.name = component_name

      defn.set_attribute(VCAD_DICT, 'node_id', node_id)
      defn.set_attribute(VCAD_DICT, 'source_file', source_file)
      defn.set_attribute(VCAD_DICT, 'version', 1)

      pt = Geom::Point3d.new(
        position[0].to_f.mm,
        position[1].to_f.mm,
        position[2].to_f.mm
      )
      tr = Geom::Transformation.new(pt)
      instance = model.active_entities.add_instance(defn, tr)

      model.commit_operation

      {
        success: true,
        node_id: node_id,
        entity_id: instance.entityID,
        definition_name: defn.name
      }
    end

    # Re-import OBJ using atomic definition swap + rollback on failure.
    # Never mutate the existing definition in place.
    # @param params [Hash] parameters: obj_path, node_id, source_file
    # @param workspace [String, nil] workspace path for path validation
    # @return [Hash] result with version, replaced_instances count
    def update_vcad_node(params, workspace: nil)
      obj_path = params['obj_path']
      node_id = params['node_id']
      source_file = params['source_file']

      PathPolicy.validate!(obj_path, operation: 'vcad import', workspace: workspace)
      PathPolicy.validate!(source_file, operation: 'vcad source', workspace: workspace) if source_file

      model = Sketchup.active_model
      old_defn = find_vcad_definition(model, node_id)
      raise "vcad node not found: #{node_id}" unless old_defn

      model.start_operation('Update vcad node', true)

      begin
        placements = old_defn.instances.map do |inst|
          {
            parent_entities: inst.parent.entities,
            transformation: inst.transformation,
            layer: inst.respond_to?(:layer) ? inst.layer : nil,
            material: inst.respond_to?(:material) ? inst.material : nil,
            name: inst.respond_to?(:name) ? inst.name : nil
          }
        end

        old_name = old_defn.name
        version = old_defn.get_attribute(VCAD_DICT, 'version', 0).to_i + 1

        # SketchUp 2026: import returns the new ComponentDefinition directly.
        new_defn = model.definitions.import(obj_path)
        unless new_defn.is_a?(Sketchup::ComponentDefinition)
          raise "IMPORT_DEFINITION_NOT_FOUND: #{obj_path}"
        end
        # Keep the new definition hidden from UI naming collisions until swap is complete.
        new_defn.name = "#{old_name}__updating"
        new_defn.set_attribute(VCAD_DICT, 'node_id', node_id)
        new_defn.set_attribute(VCAD_DICT, 'source_file', source_file || old_defn.get_attribute(VCAD_DICT, 'source_file'))
        new_defn.set_attribute(VCAD_DICT, 'version', version)

        # Rebind every instance to the new definition at the same transform.
        old_instances = old_defn.instances.to_a
        placements.each_with_index do |placement, idx|
          replacement = placement[:parent_entities].add_instance(new_defn, placement[:transformation])
          replacement.layer = placement[:layer] if placement[:layer]
          replacement.material = placement[:material] if placement[:material]
          replacement.name = placement[:name] if placement[:name] && replacement.respond_to?(:name=)
          old_instances[idx]&.erase!
        end

        # Finalize naming and cleanup old definition when no instances remain.
        old_defn.name = "#{old_name}__old"
        new_defn.name = old_name
        model.definitions.remove(old_defn) if old_defn.instances.empty?

        model.commit_operation
        {
          success: true,
          node_id: node_id,
          version: version,
          definition_name: new_defn.name,
          replaced_instances: placements.length
        }
      rescue StandardError => e
        model.abort_operation
        raise "Update vcad node failed: #{e.message}"
      end
    end

    # List all vcad nodes in the model
    # @param _params [Hash] unused
    # @param workspace [String, nil] unused
    # @return [Array<Hash>] list of vcad node metadata
    def list_vcad_nodes(_params = {}, workspace: nil)
      model = Sketchup.active_model
      nodes = model.definitions.select { |d| d.get_attribute(VCAD_DICT, 'node_id') }
      nodes.map do |d|
        {
          node_id: d.get_attribute(VCAD_DICT, 'node_id'),
          source_file: d.get_attribute(VCAD_DICT, 'source_file'),
          version: d.get_attribute(VCAD_DICT, 'version'),
          name: d.name,
          instances: d.instances.length
        }
      end
    end

    # Get single vcad node metadata
    # @param params [Hash] parameters: node_id
    # @param workspace [String, nil] unused
    # @return [Hash] vcad node metadata with bounds
    def get_vcad_node(params, workspace: nil)
      node_id = params['node_id']
      model = Sketchup.active_model
      defn = find_vcad_definition(model, node_id)
      raise "vcad node not found: #{node_id}" unless defn

      {
        node_id: node_id,
        source_file: defn.get_attribute(VCAD_DICT, 'source_file'),
        version: defn.get_attribute(VCAD_DICT, 'version'),
        name: defn.name,
        instances: defn.instances.length,
        bounds: bounds_to_hash(defn.bounds)
      }
    end

    private

    def find_vcad_definition(model, node_id)
      model.definitions.find { |d| d.get_attribute(VCAD_DICT, 'node_id') == node_id }
    end

    def bounds_to_hash(bb)
      {
        min: [bb.min.x.to_mm, bb.min.y.to_mm, bb.min.z.to_mm],
        max: [bb.max.x.to_mm, bb.max.y.to_mm, bb.max.z.to_mm]
      }
    end
  end
end
