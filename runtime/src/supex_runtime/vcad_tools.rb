# frozen_string_literal: true

require_relative 'path_policy'

module SupexRuntime
  # Tool implementations for VCAD node management in SketchUp.
  # Handles mesh import, VCAD attribute storage, and instance lifecycle.
  module VCADTools
    extend self

    VCAD_DICT = 'vcad'

    # Import mesh (DAE) as ComponentDefinition, set VCAD attributes, place instance
    # @param params [Hash] parameters: mesh_path, node_id, source_file, component_name, position
    # @param workspace [String, nil] workspace path for path validation
    # @return [Hash] result with entity_id, definition_name
    def place_vcad_node(params, workspace: nil)
      mesh_path = params['mesh_path']
      node_id = params['node_id']
      source_file = params['source_file']
      component_name = params['component_name'] || "vcad_#{node_id}"
      position = params['position'] || [0, 0, 0]

      PathPolicy.validate!(mesh_path, operation: 'VCAD import', workspace: workspace)
      PathPolicy.validate!(source_file, operation: 'VCAD source', workspace: workspace) if source_file

      model = Sketchup.active_model
      model.start_operation('Place VCAD node', true)

      # SketchUp 2026: definitions.import returns ComponentDefinition.
      defn = model.definitions.import(mesh_path)
      raise "IMPORT_DEFINITION_NOT_FOUND: #{mesh_path}" unless defn.is_a?(Sketchup::ComponentDefinition)

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

    # Re-import mesh (DAE) using atomic definition swap + rollback on failure.
    # Never mutate the existing definition in place.
    # @param params [Hash] parameters: mesh_path, node_id, source_file
    # @param workspace [String, nil] workspace path for path validation
    # @return [Hash] result with version, replaced_instances count
    def update_vcad_node(params, workspace: nil)
      mesh_path = params['mesh_path']
      node_id = params['node_id']
      source_file = params['source_file']

      PathPolicy.validate!(mesh_path, operation: 'VCAD import', workspace: workspace)
      PathPolicy.validate!(source_file, operation: 'VCAD source', workspace: workspace) if source_file

      model = Sketchup.active_model
      old_defn = find_vcad_definition(model, node_id)
      raise "VCAD node not found: #{node_id}" unless old_defn

      model.start_operation('Update VCAD node', true)

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
        new_defn = model.definitions.import(mesh_path)
        raise "IMPORT_DEFINITION_NOT_FOUND: #{mesh_path}" unless new_defn.is_a?(Sketchup::ComponentDefinition)

        # Keep the new definition hidden from UI naming collisions until swap is complete.
        new_defn.name = "#{old_name}__updating"
        new_defn.set_attribute(VCAD_DICT, 'node_id', node_id)
        new_defn.set_attribute(VCAD_DICT, 'source_file',
                               source_file || old_defn.get_attribute(VCAD_DICT, 'source_file'))
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
        raise "Update VCAD node failed: #{e.message}"
      end
    end

    # List all VCAD nodes in the model
    # @param _params [Hash] unused
    # @param workspace [String, nil] unused
    # @return [Array<Hash>] list of VCAD node metadata
    def list_vcad_nodes(_params = {}, workspace: nil) # rubocop:disable Lint/UnusedMethodArgument
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

    # Get single VCAD node metadata
    # @param params [Hash] parameters: node_id
    # @param workspace [String, nil] unused
    # @return [Hash] VCAD node metadata with bounds
    def get_vcad_node(params, workspace: nil) # rubocop:disable Lint/UnusedMethodArgument
      node_id = params['node_id']
      model = Sketchup.active_model
      defn = find_vcad_definition(model, node_id)
      raise "VCAD node not found: #{node_id}" unless defn

      {
        node_id: node_id,
        source_file: defn.get_attribute(VCAD_DICT, 'source_file'),
        version: defn.get_attribute(VCAD_DICT, 'version'),
        name: defn.name,
        instances: defn.instances.length,
        bounds: bounds_to_hash(defn.bounds)
      }
    end

    # Resolve a VCAD data import from a SketchUp entity.
    # Extracts dimensions, bbox, or transform from the entity identified by entity_id.
    # @param params [Hash] parameters: entity_id, extract
    # @param workspace [String, nil] unused
    # @return [Hash] resolved data with vcad_node_id
    def resolve_vcad_import(params, workspace: nil) # rubocop:disable Lint/UnusedMethodArgument
      entity_id = params['entity_id'].to_i
      extract_type = params['extract']

      entity = Sketchup.active_model.find_entity_by_id(entity_id)
      raise "Entity not found: #{entity_id}" unless entity

      defn = entity.respond_to?(:definition) ? entity.definition : nil
      vcad_node_id = defn&.get_attribute(VCAD_DICT, 'node_id')

      case extract_type
      when 'all'
        bb = entity.bounds
        { extract: 'all', vcad_node_id: vcad_node_id,
          data: {
            dims: { width: bb.width.to_mm, height: bb.height.to_mm, depth: bb.depth.to_mm },
            bbox: { min: [bb.min.x.to_mm, bb.min.y.to_mm, bb.min.z.to_mm],
                    max: [bb.max.x.to_mm, bb.max.y.to_mm, bb.max.z.to_mm] },
            transform: { matrix: entity.respond_to?(:transformation) ? entity.transformation.to_a : nil }
          } }
      when 'dims'
        bb = entity.bounds
        { extract: 'dims', vcad_node_id: vcad_node_id,
          data: { width: bb.width.to_mm, height: bb.height.to_mm, depth: bb.depth.to_mm } }
      when 'bbox'
        bb = entity.bounds
        { extract: 'bbox', vcad_node_id: vcad_node_id,
          data: { min: [bb.min.x.to_mm, bb.min.y.to_mm, bb.min.z.to_mm],
                  max: [bb.max.x.to_mm, bb.max.y.to_mm, bb.max.z.to_mm] } }
      when 'transform'
        raise "Entity #{entity_id} has no transformation" unless entity.respond_to?(:transformation)

        { extract: 'transform', vcad_node_id: vcad_node_id,
          data: { matrix: entity.transformation.to_a } }
      when 'solid'
        if vcad_node_id
          { extract: 'solid', source: 'vcad', vcad_node_id: vcad_node_id }
        elsif defn && defn.entities.grep(Sketchup::Face).any?
          mesh_data = extract_solid_mesh(defn)
          { extract: 'solid', source: 'native_mesh', mesh: mesh_data }
        else
          raise "Entity #{entity_id} is not a solid — :solid import unavailable"
        end
      else
        raise "Unsupported extract type: #{extract_type}"
      end
    end

    private

    # Extract triangulated mesh from a SketchUp solid (manifold ComponentDefinition).
    # Returns { positions: [f64], indices: [u32], normals: [f64] } in mm units.
    def extract_solid_mesh(defn)
      positions = []
      indices = []
      normals = []
      vertex_offset = 0

      defn.entities.grep(Sketchup::Face).each do |face|
        mesh = face.mesh(0) # 0 = no UVs, just geometry
        # PolygonMesh: vertices are 1-based
        mesh.count_points.times do |i|
          pt = mesh.point_at(i + 1)
          positions.push(pt.x.to_mm, pt.y.to_mm, pt.z.to_mm)
          n = mesh.normal_at(i + 1)
          normals.push(n.x, n.y, n.z)
        end
        mesh.count_polygons.times do |i|
          tri = mesh.polygon_at(i + 1) # returns array of vertex indices (1-based, may be negative)
          tri.each { |vi| indices.push(vi.abs - 1 + vertex_offset) }
        end
        vertex_offset += mesh.count_points
      end

      { positions: positions, indices: indices, normals: normals }
    end

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
