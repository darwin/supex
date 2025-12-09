# frozen_string_literal: true

require 'fileutils'
require_relative 'utils'
require_relative 'batch_screenshot'

module SupexRuntime
  # Tool implementations for the Supex server
  # Extracted from BridgeServer class to reduce class length
  module Tools
    # Get basic information about the current SketchUp model
    # @return [Hash] model statistics and metadata
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
    # @return [Hash] screenshot result with file path (not image data)
    def take_screenshot(params)
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      screenshot_path = determine_screenshot_path(params['output_path'])
      write_screenshot(model, screenshot_path, params)
    rescue StandardError => e
      log "Error taking screenshot: #{e.message}"
      log e.backtrace.join("\n")
      raise "Failed to take screenshot: #{e.message}"
    end

    # Take batch screenshots with different camera positions
    # Designed for zero visual flicker - renders happen offscreen
    # @param params [Hash] batch screenshot parameters
    # @return [Hash] batch results with file paths
    def batch_screenshot(params)
      BatchScreenshot.execute(params)
    rescue StandardError => e
      log "Error taking batch screenshots: #{e.message}"
      log e.backtrace.join("\n")
      raise "Failed to take batch screenshots: #{e.message}"
    end

    # Open a SketchUp model file
    # @param params [Hash] parameters with file path
    # @return [Hash] open operation result
    def open_model(params)
      file_path = params['path']
      return { success: false, error: 'No file path provided' } unless file_path
      return { success: false, error: "File not found: #{file_path}" } unless File.exist?(file_path)

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
    # @return [Hash] save operation result
    def save_model(params)
      model = Sketchup.active_model
      return { success: false, error: 'No active model' } unless model

      saved_path = perform_save(model, params['path'])
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

    def determine_screenshot_path(output_path)
      if output_path
        path = File.expand_path(output_path)
        FileUtils.mkdir_p(File.dirname(path))
        path
      else
        screenshots_dir = File.join(File.dirname(__FILE__), '..', '..', '..', '.tmp', 'screenshots')
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
