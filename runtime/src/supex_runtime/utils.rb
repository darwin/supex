# frozen_string_literal: true

module SupexRuntime
  # Utility functions for the Supex extension
  module Utils
    # Convert SketchUp bounds to hash format
    # @param bounds [Geom::BoundingBox] SketchUp bounding box
    # @return [Hash] bounds as hash with min, max, center coordinates
    def self.bounds_to_hash(bounds)
      {
        min: [bounds.min.x, bounds.min.y, bounds.min.z],
        max: [bounds.max.x, bounds.max.y, bounds.max.z],
        center: [bounds.center.x, bounds.center.y, bounds.center.z]
      }
    end

    # Safe console output for SketchUp
    # @param message [String] message to output
    def self.console_write(message)
      # Use puts to ensure console capture works and appears in SketchUp console
      puts message
    end

    # Show SketchUp console with multiple fallback methods
    def self.show_console
      SKETCHUP_CONSOLE.show
    rescue StandardError
      begin
        Sketchup.send_action('showRubyPanel:')
      rescue StandardError
        UI.start_timer(0) { SKETCHUP_CONSOLE.show }
      end
    end

    # Validate SketchUp entity exists and is valid
    # @param entity_id [Integer] SketchUp entity ID
    # @return [Sketchup::Entity, nil] entity if found and valid
    def self.find_entity(entity_id)
      model = Sketchup.active_model
      entity = model.find_entity_by_id(entity_id.to_i)
      entity if entity&.valid?
    end

    # Safe entity ID extraction with string cleaning
    # @param id [String, Integer] entity ID (may have quotes)
    # @return [Integer] clean entity ID
    def self.clean_entity_id(id)
      id.to_s.gsub('"', '').to_i
    end

    # Create circle points for cylindrical shapes
    # @param center [Array<Float>] center point [x, y, z]
    # @param radius [Float] circle radius
    # @param segments [Integer] number of segments
    # @return [Array<Array<Float>>] array of point coordinates
    def self.create_circle_points(center, radius, segments = 24)
      points = []
      segments.times do |i|
        angle = Math::PI * 2 * i / segments
        x = center[0] + (radius * Math.cos(angle))
        y = center[1] + (radius * Math.sin(angle))
        z = center[2]
        points << [x, y, z]
      end
      points
    end

    # Safe JSON-RPC response creation
    # @param request [Hash] original JSON-RPC request
    # @param result [Hash] result data
    # @return [Hash] formatted JSON-RPC response
    def self.create_success_response(request, result)
      {
        jsonrpc: request['jsonrpc'] || '2.0',
        result: result,
        id: request['id']
      }
    end

    # Safe JSON-RPC error response creation
    # @param request [Hash] original JSON-RPC request
    # @param error_message [String] error message
    # @param error_code [Integer] JSON-RPC error code
    # @return [Hash] formatted JSON-RPC error response
    def self.create_error_response(request, error_message, error_code = -32_603)
      {
        jsonrpc: request['jsonrpc'] || '2.0',
        error: {
          code: error_code,
          message: error_message,
          data: { success: false }
        },
        id: request['id']
      }
    end
  end
end
