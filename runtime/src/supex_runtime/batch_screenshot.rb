# frozen_string_literal: true

require 'fileutils'

module SupexRuntime
  # Batch screenshot functionality with zero-flicker camera control
  #
  # This module enables taking multiple screenshots with different camera positions
  # in a single batch operation, designed to minimize or eliminate visual flicker
  # for the SketchUp user.
  #
  # Zero-flicker strategy:
  # 1. Use start_operation with disable_ui=true to suppress UI updates
  # 2. write_image renders offscreen when dimensions differ from viewport
  # 3. Process all shots rapidly in sequence
  # 4. Restore original camera immediately after batch completes
  module BatchScreenshot
    # Standard view camera configurations
    # Direction points FROM camera TO model center, Up defines camera orientation
    STANDARD_VIEWS = {
      'top' => { direction: [0, 0, -1], up: [0, 1, 0] },
      'bottom' => { direction: [0, 0, 1], up: [0, -1, 0] },
      'front' => { direction: [0, 1, 0], up: [0, 0, 1] },
      'back' => { direction: [0, -1, 0], up: [0, 0, 1] },
      'left' => { direction: [1, 0, 0], up: [0, 0, 1] },
      'right' => { direction: [-1, 0, 0], up: [0, 0, 1] },
      'iso' => { direction: [-1, -1, -1], up: [0, 0, 1] }
    }.freeze

    class << self
      # Execute batch screenshot operation
      # @param params [Hash] batch parameters
      # @return [Hash] results with file paths and any errors
      def execute(params)
        model = Sketchup.active_model
        return { success: false, error: 'No active model' } unless model

        shots = params['shots'] || []
        return { success: false, error: 'No shots specified' } if shots.empty?

        view = model.active_view
        output_dir = prepare_output_dir(params['output_dir'])
        base_name = params['base_name'] || 'screenshot'
        defaults = extract_defaults(params)

        # Save original camera state for restoration
        original_camera = save_camera_state(view.camera)

        # Process all shots with UI suppression for zero-flicker
        results = process_shots_with_ui_suppression(
          model, view, shots, output_dir, base_name, defaults
        )

        # Restore original camera if requested (default: true)
        restore_camera_state(view, original_camera) if params['restore_camera'] != false

        build_response(results, output_dir)
      rescue StandardError => e
        { success: false, error: e.message, backtrace: e.backtrace.first(5) }
      end

      private

      # Process all shots within a single operation for UI suppression
      # @param model [Sketchup::Model] the model
      # @param view [Sketchup::View] the view
      # @param shots [Array<Hash>] shot specifications
      # @param output_dir [String] output directory path
      # @param base_name [String] base filename
      # @param defaults [Hash] default parameters
      # @return [Array<Hash>] results for each shot
      def process_shots_with_ui_suppression(model, view, shots, output_dir, base_name, defaults)
        results = []

        # Use start_operation with disable_ui=true to suppress UI updates
        # This minimizes flicker during rapid camera changes
        model.start_operation('Batch Screenshot', true)

        begin
          shots.each_with_index do |shot, index|
            result = process_single_shot(view, model, shot, output_dir, base_name, index, defaults)
            results << result
          end
          model.commit_operation
        rescue StandardError => e
          model.abort_operation
          raise e
        end

        results
      end

      # Process a single shot
      # @param view [Sketchup::View] the view
      # @param model [Sketchup::Model] the model
      # @param shot [Hash] shot specification
      # @param output_dir [String] output directory
      # @param base_name [String] base filename
      # @param index [Integer] shot index
      # @param defaults [Hash] default parameters
      # @return [Hash] result for this shot
      def process_single_shot(view, model, shot, output_dir, base_name, index, defaults)
        camera_spec = shot['camera'] || {}
        shot_name = shot['name'] || format('%03d', index)

        width = shot['width'] || defaults[:width]
        height = shot['height'] || defaults[:height]

        begin
          # Apply camera for this shot
          apply_camera(view, model, camera_spec)

          # Generate filename
          filename = "#{base_name}_#{shot_name}.png"
          filepath = File.join(output_dir, filename)

          # Take screenshot (offscreen render due to explicit dimensions)
          write_screenshot(view, filepath, width, height, defaults[:transparent])

          { success: true, file_path: filepath, name: shot_name }
        rescue StandardError => e
          { success: false, name: shot_name, error: e.message }
        end
      end

      # Apply camera based on specification
      # @param view [Sketchup::View] the view
      # @param model [Sketchup::Model] the model
      # @param camera_spec [Hash] camera specification
      def apply_camera(view, model, camera_spec)
        type = camera_spec['type'] || 'zoom_extents'

        case type
        when 'standard_view'
          apply_standard_view(view, model, camera_spec['view'])
        when 'custom'
          apply_custom_camera(view, camera_spec)
        when 'zoom_entity'
          apply_zoom_entity(view, model, camera_spec)
        when 'zoom_extents'
          view.zoom_extents
        else
          raise "Unknown camera type: #{type}"
        end
      end

      # Apply a standard view (top, front, iso, etc.)
      # @param view [Sketchup::View] the view
      # @param model [Sketchup::Model] the model
      # @param view_name [String] name of the standard view
      def apply_standard_view(view, model, view_name)
        config = STANDARD_VIEWS[view_name.to_s.downcase]
        raise "Unknown standard view: #{view_name}" unless config

        bounds = model.bounds
        if bounds.empty?
          # Empty model - use default camera at origin
          view.zoom_extents
          return
        end

        center = bounds.center
        diagonal = bounds.diagonal
        distance = diagonal * 1.5 # Ensure model fits in view with some margin

        direction = Geom::Vector3d.new(*config[:direction]).normalize
        up = Geom::Vector3d.new(*config[:up])

        eye = center.offset(direction.reverse, distance)

        camera = Sketchup::Camera.new(eye, center, up)
        camera.perspective = false # Standard views use parallel projection
        view.camera = camera
      end

      # Apply custom camera coordinates
      # @param view [Sketchup::View] the view
      # @param camera_spec [Hash] camera specification with eye, target, up
      def apply_custom_camera(view, camera_spec)
        eye = Geom::Point3d.new(*camera_spec['eye'])
        target = Geom::Point3d.new(*camera_spec['target'])
        up_array = camera_spec['up'] || [0, 0, 1]
        up = Geom::Vector3d.new(*up_array)

        perspective = camera_spec['perspective'] != false
        fov = camera_spec['fov'] || 35.0

        camera = Sketchup::Camera.new(eye, target, up, perspective, fov)
        view.camera = camera
      end

      # Zoom to specific entities by ID
      # @param view [Sketchup::View] the view
      # @param model [Sketchup::Model] the model
      # @param camera_spec [Hash] camera specification with entity_ids
      def apply_zoom_entity(view, model, camera_spec)
        entity_ids = camera_spec['entity_ids'] || []
        raise 'No entity_ids specified for zoom_entity' if entity_ids.empty?

        entities = entity_ids.map { |id| model.find_entity_by_id(id) }.compact
        raise "No valid entities found for IDs: #{entity_ids}" if entities.empty?

        # Zoom to the entities
        view.zoom(entities)

        # Apply padding if specified
        padding = camera_spec['padding'] || 1.0
        apply_zoom_padding(view, padding) if padding != 1.0
      end

      # Apply zoom padding by adjusting camera distance
      # @param view [Sketchup::View] the view
      # @param padding [Float] padding factor (1.0 = no change, 1.2 = 20% margin)
      def apply_zoom_padding(view, padding)
        camera = view.camera
        if camera.perspective?
          # For perspective, move camera back
          direction = camera.direction
          eye = camera.eye
          target = camera.target
          distance = eye.distance(target)
          new_distance = distance * padding
          new_eye = target.offset(direction.reverse, new_distance)
          camera.set(new_eye, target, camera.up)
        else
          # For parallel projection, increase height
          camera.height = camera.height * padding
        end
        view.camera = camera
      end

      # Save camera state for later restoration
      # @param camera [Sketchup::Camera] the camera
      # @return [Hash] saved camera state
      def save_camera_state(camera)
        {
          eye: camera.eye.to_a,
          target: camera.target.to_a,
          up: camera.up.to_a,
          fov: camera.fov,
          perspective: camera.perspective?,
          height: camera.perspective? ? nil : camera.height
        }
      end

      # Restore camera to saved state
      # @param view [Sketchup::View] the view
      # @param state [Hash] saved camera state
      def restore_camera_state(view, state)
        eye = Geom::Point3d.new(*state[:eye])
        target = Geom::Point3d.new(*state[:target])
        up = Geom::Vector3d.new(*state[:up])

        camera = Sketchup::Camera.new(eye, target, up, state[:perspective], state[:fov])
        camera.height = state[:height] unless state[:perspective]
        view.camera = camera
      end

      # Write screenshot to file
      # @param view [Sketchup::View] the view
      # @param filepath [String] output file path
      # @param width [Integer] image width
      # @param height [Integer] image height
      # @param transparent [Boolean] use transparent background
      def write_screenshot(view, filepath, width, height, transparent)
        FileUtils.mkdir_p(File.dirname(filepath))

        options = {
          filename: filepath,
          width: width,
          height: height,
          antialias: true,
          compression: 0.9,
          transparent: transparent
        }

        view.write_image(options)
      end

      # Prepare output directory
      # @param output_dir [String, nil] requested output directory
      # @return [String] resolved output directory path
      def prepare_output_dir(output_dir)
        dir = if output_dir
                File.expand_path(output_dir)
              else
                timestamp = Time.now.strftime('%Y%m%d-%H%M%S')
                File.join(File.dirname(__FILE__), '..', '..', '..', '.tmp', 'batch_screenshots', timestamp)
              end
        FileUtils.mkdir_p(dir)
        dir
      end

      # Extract default parameters from params hash
      # @param params [Hash] input parameters
      # @return [Hash] default values
      def extract_defaults(params)
        {
          width: params['width'] || 1920,
          height: params['height'] || 1080,
          transparent: params['transparent'] || false
        }
      end

      # Build response hash
      # @param results [Array<Hash>] results for each shot
      # @param output_dir [String] output directory path
      # @return [Hash] response
      def build_response(results, output_dir)
        successful = results.count { |r| r[:success] }
        failed = results.count { |r| !r[:success] }

        {
          success: failed.zero?,
          output_dir: output_dir,
          total_shots: results.length,
          successful: successful,
          failed: failed,
          results: results
        }
      end
    end
  end
end
