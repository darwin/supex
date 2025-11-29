# frozen_string_literal: true

require 'fileutils'

module SupexRuntime
  # Export functionality for SketchUp models
  module Export
    # Supported export formats
    SUPPORTED_FORMATS = %w[skp obj stl png jpg jpeg].freeze

    # Export the current SketchUp scene
    # @param params [Hash] export parameters
    # @option params [String] 'format' export format (skp, obj, stl, png, jpg)
    # @option params [Integer] 'width' image width (for image exports)
    # @option params [Integer] 'height' image height (for image exports)
    # @return [Hash] result with export path and format
    def self.export_scene(params)
      format = params['format'] || 'skp'

      unless SUPPORTED_FORMATS.include?(format.downcase)
        raise "Unsupported export format: #{format}"
      end

      model = Sketchup.active_model
      export_path = generate_export_path(format)

      case format.downcase
      when 'skp'
        export_skp(model, export_path)
      when 'obj'
        export_obj(model, export_path)
      when 'stl'
        export_stl(model, export_path)
      when 'png', 'jpg', 'jpeg'
        export_image(model, export_path, format, params)
      end

      {
        success: true,
        path: export_path,
        format: format
      }
    end

    # Generate export file path with timestamp
    # @param format [String] file format
    # @return [String] full export path
    def self.generate_export_path(format)
      temp_dir = File.join(ENV['TEMP'] || ENV['TMP'] || Dir.tmpdir, 'supex_runtime_exports')
      FileUtils.mkdir_p(temp_dir)

      timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
      filename = "supex_runtime_export_#{timestamp}"
      extension = format.downcase == 'jpg' ? 'jpeg' : format.downcase

      File.join(temp_dir, "#{filename}.#{extension}")
    end

    # Export as SketchUp native format
    # @param model [Sketchup::Model] SketchUp model
    # @param path [String] export path
    def self.export_skp(model, path)
      model.save(path)
    end

    # Export as OBJ format
    # @param model [Sketchup::Model] SketchUp model
    # @param path [String] export path
    def self.export_obj(model, path)
      options = {
        triangulated_faces: true,
        double_sided_faces: true,
        edges: false,
        texture_maps: true
      }
      model.export(path, options)
    end

    # Export as STL format
    # @param model [Sketchup::Model] SketchUp model
    # @param path [String] export path
    def self.export_stl(model, path)
      options = { units: 'model' }
      model.export(path, options)
    end

    # Export as image format
    # @param model [Sketchup::Model] SketchUp model
    # @param path [String] export path
    # @param format [String] image format
    # @param params [Hash] export parameters
    def self.export_image(model, path, format, params)
      view = model.active_view

      options = {
        filename: path,
        width: params['width'] || 1920,
        height: params['height'] || 1080,
        antialias: true,
        transparent: format.downcase == 'png'
      }

      view.write_image(options)
    end
  end
end
