# frozen_string_literal: true

require 'fileutils'
require_relative 'utils'
require_relative 'batch_screenshot'
require_relative 'path_policy'

module SupexRuntime
  # Tool implementations for the Supex server
  # Extracted from BridgeServer class to reduce class length
  module Tools
    # Get basic information about the current SketchUp model
    # @return [Hash] model statistics and metadata; +path+ is nil for an unsaved model
    def model_info
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      build_model_info_response(model)
    rescue StandardError => e
      log "Error getting model info: #{e.message}"
      raise "Failed to get model info: #{e.message}"
    end

    # List entities in the model
    # @param params [Hash] parameters with optional entity_type filter
    # @return [Hash] list of entities
    def list_entities(params)
      model = Sketchup.active_model
      entity_type = params['entity_type'] || 'all'
      return { success: false, error: 'No active model' } unless model

      entities = filter_entities_by_type(model, entity_type)
      entities_data = entities.map { |entity| build_entity_data(entity) }

      { success: true, entity_type: entity_type, count: entities_data.length,
        entities: entities_data }
    rescue StandardError => e
      log "Error listing entities: #{e.message}"
      raise "Failed to list entities: #{e.message}"
    end

    # Get currently selected entities
    # @return [Hash] selection information
    def selection_info
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      entities_data = model.selection.map { |entity| build_selection_entity_data(entity) }
      { success: true, count: model.selection.count, entities: entities_data }
    rescue StandardError => e
      log "Error getting selection: #{e.message}"
      raise "Failed to get selection: #{e.message}"
    end

    # Get detailed state of a single entity by ID
    # @param params [Hash] parameters with entity_id
    # @return [Hash] entity type, name, layer, material, visibility, bounds, dimensions and
    #   (for groups and component instances) transformation and definition
    def get_entity(params)
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      entity_id = params['entity_id']
      return { success: false, error: 'No entity_id provided' } unless entity_id

      entity = model.find_entity_by_id(entity_id.to_i)
      return { success: false, error: "Entity not found: #{entity_id}" } unless entity&.valid?

      { success: true }.merge(build_entity_detail(entity))
    end

    # Get list of layers (tags) in the model
    # @return [Hash] layers information
    def layers_info
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      layers_data = model.layers.map do |layer|
        { name: layer.name, visible: layer.visible?, page_behavior: layer.page_behavior }
      end
      { success: true, count: layers_data.length, layers: layers_data }
    rescue StandardError => e
      log "Error getting layers: #{e.message}"
      raise "Failed to get layers: #{e.message}"
    end

    # Get list of materials in the model
    # @return [Hash] materials information
    def materials_info
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      materials_data = model.materials.map { |material| build_material_data(material) }
      { success: true, count: materials_data.length, materials: materials_data }
    rescue StandardError => e
      log "Error getting materials: #{e.message}"
      raise "Failed to get materials: #{e.message}"
    end

    # Get current camera information
    # @return [Hash] camera settings
    def camera_info
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      build_camera_info_response(model)
    rescue StandardError => e
      log "Error getting camera info: #{e.message}"
      raise "Failed to get camera info: #{e.message}"
    end

    # Take a screenshot of the current view and save to disk
    # @param params [Hash] parameters with width, height, transparent, output_path
    # @param workspace [String, nil] workspace path for default output directory
    # @return [Hash] screenshot result with file path (not image data)
    def take_screenshot(params, workspace: nil)
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      # Validate output_path if provided (resolves relative paths against workspace)
      output_path = PathPolicy.validate!(params['output_path'], operation: 'take_screenshot',
                                                                workspace: workspace)

      screenshot_path = determine_screenshot_path(output_path, workspace)
      write_screenshot(model, screenshot_path, params)
    rescue StandardError => e
      log "Error taking screenshot: #{e.message}"
      log e.backtrace.join("\n")
      raise "Failed to take screenshot: #{e.message}"
    end

    # Take batch screenshots with different camera positions
    # Designed for zero visual flicker - renders happen offscreen
    # @param params [Hash] batch screenshot parameters
    # @param workspace [String, nil] workspace path for default output directory
    # @return [Hash] batch results with file paths
    def batch_screenshot(params, workspace: nil)
      BatchScreenshot.execute(params, workspace: workspace)
    rescue StandardError => e
      log "Error taking batch screenshots: #{e.message}"
      log e.backtrace.join("\n")
      raise "Failed to take batch screenshots: #{e.message}"
    end

    # Open a SketchUp model file
    # @param params [Hash] parameters with file path
    # @param workspace [String, nil] workspace path for path validation
    # @return [Hash] open operation result
    def open_model(params, workspace: nil)
      return { success: false, error: 'No file path provided' } unless params['path']

      file_path = PathPolicy.validate!(params['path'], operation: 'open_model', workspace: workspace)
      return { success: false, error: "File not found: #{params['path']}" } unless File.exist?(file_path)

      Sketchup.open_file(file_path)
      model = Sketchup.active_model
      { success: true, file_path: file_path, file_name: File.basename(file_path),
        title: model.title }
    rescue StandardError => e
      log "Error opening model: #{e.message}"
      raise "Failed to open model: #{e.message}"
    end

    # Save the current model
    # @param params [Hash] parameters with optional save path
    # @param workspace [String, nil] workspace path for path validation
    # @return [Hash] save operation result
    def save_model(params, workspace: nil)
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      # Validate path if provided (resolves relative paths against workspace)
      save_path = PathPolicy.validate!(params['path'], operation: 'save_model', workspace: workspace)

      saved_path = perform_save(model, save_path)
      { success: true, file_path: saved_path, file_name: File.basename(saved_path),
        title: model.title }
    rescue StandardError => e
      log "Error saving model: #{e.message}"
      raise "Failed to save model: #{e.message}"
    end

    private

    def build_model_info_response(model)
      units_options = model.options['UnitsOptions']
      length_unit = units_options['LengthUnit']
      units_map = { 0 => 'inches', 1 => 'feet', 2 => 'millimeters', 3 => 'centimeters',
                    4 => 'meters' }

      {
        success: true,
        title: model.title.empty? ? 'Untitled' : model.title,
        path: model.path.to_s.empty? ? nil : model.path.to_s,
        units: units_map[length_unit] || 'unknown',
        num_faces: model.entities.grep(Sketchup::Face).count,
        num_edges: model.entities.grep(Sketchup::Edge).count,
        num_groups: model.entities.grep(Sketchup::Group).count,
        num_components: model.entities.grep(Sketchup::ComponentInstance).count,
        modified: model.modified?
      }
    end

    def filter_entities_by_type(model, entity_type)
      case entity_type
      when 'faces' then model.entities.grep(Sketchup::Face)
      when 'edges' then model.entities.grep(Sketchup::Edge)
      when 'groups' then model.entities.grep(Sketchup::Group)
      when 'components' then model.entities.grep(Sketchup::ComponentInstance)
      else model.entities.to_a
      end
    end

    def build_entity_data(entity)
      data = { type: entity.typename, entity_id: entity.entityID }

      case entity
      when Sketchup::Group
        data[:name] = entity.name.empty? ? '(unnamed)' : entity.name
        data[:layer] = entity.layer.name
      when Sketchup::ComponentInstance
        data[:name] = entity.definition.name
        data[:layer] = entity.layer.name
      when Sketchup::Face
        data[:area] = entity.area
        data[:layer] = entity.layer.name
      when Sketchup::Edge
        data[:length] = entity.length
        data[:layer] = entity.layer.name
      end

      data
    end

    # Full state of one entity; lengths are in inches (SketchUp internal units)
    def build_entity_detail(entity)
      data = build_entity_data(entity)
      data[:persistent_id] = entity.persistent_id if entity.respond_to?(:persistent_id)
      data[:layer] = entity.layer.name if !data.key?(:layer) && entity.respond_to?(:layer)
      add_bounds_data(data, entity)
      add_drawingelement_data(data, entity)
      add_instance_data(data, entity)
      data
    end

    def add_bounds_data(data, entity)
      return unless entity.respond_to?(:bounds)

      bounds = entity.bounds
      return if bounds.empty?

      min = bounds.min
      max = bounds.max
      data[:bounds] = {
        min: [min.x.to_f, min.y.to_f, min.z.to_f],
        max: [max.x.to_f, max.y.to_f, max.z.to_f]
      }
      data[:dimensions] = {
        width: (max.x - min.x).to_f,
        depth: (max.y - min.y).to_f,
        height: (max.z - min.z).to_f
      }
    end

    def add_drawingelement_data(data, entity)
      data[:material] = entity.material&.name if entity.respond_to?(:material)
      data[:hidden] = entity.hidden? if entity.respond_to?(:hidden?)
      data[:visible] = entity.visible? if entity.respond_to?(:visible?)
      data[:locked] = entity.locked? if entity.respond_to?(:locked?)
    end

    def add_instance_data(data, entity)
      return unless entity.is_a?(Sketchup::Group) || entity.is_a?(Sketchup::ComponentInstance)

      data[:instance_name] = entity.name if entity.is_a?(Sketchup::ComponentInstance)
      data[:definition] = entity.definition.name if entity.respond_to?(:definition)
      return unless entity.respond_to?(:transformation)

      transformation = entity.transformation
      origin = transformation.origin
      data[:transformation] = transformation.to_a.map(&:to_f)
      data[:origin] = [origin.x.to_f, origin.y.to_f, origin.z.to_f]
    end

    def build_selection_entity_data(entity)
      data = { type: entity.typename, entity_id: entity.entityID }

      case entity
      when Sketchup::Face
        data[:area] = entity.area
        normal = entity.normal
        data[:normal] = [normal.x, normal.y, normal.z]
      when Sketchup::Edge
        data[:length] = entity.length
      when Sketchup::Group
        data[:name] = entity.name.empty? ? '(unnamed)' : entity.name
      when Sketchup::ComponentInstance
        data[:name] = entity.definition.name
      end

      data
    end

    def build_material_data(material)
      data = { name: material.name, display_name: material.display_name }

      if material.color
        data[:color] = {
          red: material.color.red, green: material.color.green,
          blue: material.color.blue, alpha: material.alpha
        }
      end

      data[:textured] = !material.texture.nil?
      data
    end

    def build_camera_info_response(model)
      camera = model.active_view.camera
      eye = camera.eye
      target = camera.target
      up = camera.up

      {
        success: true,
        eye: [eye.x, eye.y, eye.z],
        target: [target.x, target.y, target.z],
        up: [up.x, up.y, up.z],
        fov: camera.fov,
        aspect_ratio: camera.aspect_ratio,
        perspective: camera.perspective?
      }
    end

    def determine_screenshot_path(output_path, workspace)
      if output_path
        path = File.expand_path(output_path)
        FileUtils.mkdir_p(File.dirname(path))
        path
      else
        screenshots_dir = File.join(PathPolicy.default_tmp_dir(workspace), 'screenshots')
        FileUtils.mkdir_p(screenshots_dir)
        timestamp = Time.now.strftime('%Y%m%d-%H%M%S')
        File.join(screenshots_dir, "screenshot-#{timestamp}.png")
      end
    end

    def write_screenshot(model, screenshot_path, params)
      width = params['width'] || 1920
      height = params['height'] || 1080

      options = {
        filename: screenshot_path, width: width, height: height,
        antialias: true, compression: 0.9, transparent: params['transparent'] || false
      }

      model.active_view.write_image(options)

      {
        success: true, file_path: screenshot_path, file_name: File.basename(screenshot_path),
        width: width, height: height, format: 'png',
        message: "Screenshot saved to #{screenshot_path}. Use Read tool to view if needed."
      }
    end

    def perform_save(model, path)
      if path
        model.save(path)
        path
      else
        model.save
        model.path
      end
    end
  end
end
