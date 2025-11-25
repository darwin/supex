# frozen_string_literal: true

require 'json'
require 'socket'
require 'fileutils'
require_relative 'version'
require_relative 'utils'
require_relative 'export'
require_relative 'console_capture'

module SupexRuntime
  # TCP server for handling JSON-RPC requests from the Python MCP server
  class Server
    DEFAULT_PORT = 9876
    DEFAULT_HOST = '127.0.0.1'

    def initialize(port: DEFAULT_PORT, host: DEFAULT_HOST)
      @port = port
      @host = host
      @server = nil
      @running = false
      @timer_id = nil
      @console_capture = nil

      setup_console
      setup_console_capture
    end

    # Start the TCP server
    def start
      return if @running

      begin
        log "Starting Supex server on #{@host}:#{@port}..."

        @server = TCPServer.new(@host, @port)
        log "Server created on port #{@port}"

        @running = true
        start_console_capture
        start_request_handler

        log 'Supex server started and listening'
      rescue StandardError => e
        log "Error starting server: #{e.message}"
        log e.backtrace.join("\n")
        stop
      end
    end

    # Stop the TCP server
    def stop
      log 'Stopping Supex server...'
      @running = false

      stop_console_capture
      stop_timer
      close_server

      log 'Server stopped'
    end

    # Check if server is running
    # @return [Boolean] true if server is running
    def running?
      @running
    end

    private

    # Setup SketchUp console for debugging
    def setup_console
      Utils.show_console
    end

    # Setup console capture for output logging
    def setup_console_capture
      # Create .tmp directory if it doesn't exist
      tmp_dir = File.join(File.dirname(__FILE__), '..', '..', '..', '..', '.tmp')
      log_file_path = File.expand_path(File.join(tmp_dir, 'sketchup_console.log'))

      @console_capture = ConsoleCapture.new(log_file_path)
      log "Console capture initialized: #{log_file_path}"
    rescue StandardError => e
      log "Warning: Could not initialize console capture: #{e.message}"
      @console_capture = nil
    end

    # Start console output capture
    def start_console_capture
      return unless @console_capture

      @console_capture.start_capture
      @console_capture.add_marker('Supex Server Started')
    end

    # Stop console output capture
    def stop_console_capture
      return unless @console_capture

      @console_capture.add_marker('Supex Server Stopped')
      @console_capture.stop_capture
    end

    # Log message to SketchUp console
    # @param message [String] message to log
    def log(message)
      Utils.console_write("Supex: #{message}")
      $stdout.flush
    end

    # Start the request handler timer
    def start_request_handler
      # Use a more reasonable interval (0.25s) to reduce SketchUp UI load
      # This still provides responsive connection handling
      @timer_id = UI.start_timer(0.25, true) do
        handle_requests if @running
      rescue StandardError => e
        log "Timer handler error: #{e.message}"
        log e.backtrace.join("\n")
        # Don't let timer errors crash the server
      end
    end

    # Stop the timer
    def stop_timer
      return unless @timer_id

      UI.stop_timer(@timer_id)
      @timer_id = nil
    end

    # Close the server socket
    def close_server
      return unless @server

      @server.close
      @server = nil
    end

    # Handle incoming requests
    def handle_requests
      # Return early if server is not properly initialized
      return unless @server && @running

      begin
        # Check for incoming connections with a short timeout
        ready = IO.select([@server], nil, nil, 0)
        return unless ready

        log 'Connection waiting...'

        # Accept connection with timeout protection
        begin
          client = @server.accept_nonblock
          log 'Client accepted'
          process_client_request(client)
        rescue IO::WaitReadable
          # No connection actually ready, this is normal
          nil
        rescue Errno::ECONNABORTED, Errno::ECONNRESET => e
          log "Client connection error: #{e.message}"
          nil
        end
      rescue StandardError => e
        log "Server error in handle_requests: #{e.message}"
        log e.backtrace.join("\n")

        # If server socket is broken, try to recover
        if e.message.include?('closed') || e.message.include?('Bad file descriptor')
          log 'Server socket appears broken, stopping server'
          stop
        end
      end
    end

    # Process request from connected client
    # @param client [TCPSocket] client connection
    def process_client_request(client)
      # Set a reasonable timeout to prevent hanging
      client.setsockopt(Socket::SOL_SOCKET, Socket::SO_RCVTIMEO, [5, 0].pack('L!L!'))

      # Use non-blocking read with timeout
      data = read_with_timeout(client, 5.0)
      log "Raw data: #{data.inspect}"

      return unless data && !data.empty?

      begin
        # Handle potential multi-line JSON by trying to parse incrementally
        json_data = data.strip
        request = JSON.parse(json_data)
        log "Parsed request: #{request.inspect}"

        response = handle_jsonrpc_request(request)
        response_json = "#{response.to_json}\n"

        log "Sending response: #{response_json.strip}"
        client.write(response_json)
        client.flush
        log 'Response sent'

        # Give the client time to read the response before closing
        # Increased delay to ensure Python server can read response reliably
        sleep(0.25)
      rescue JSON::ParserError => e
        log "JSON parse error: #{e.message}"
        log "Raw data was: #{data.inspect}"
        send_error_response(client, 'Parse error', -32_700, nil)
      rescue StandardError => e
        log "Request error: #{e.message}"
        log e.backtrace.join("\n")
        send_error_response(client, e.message, -32_603, request&.dig('id'))
      ensure
        client.close
        log 'Client closed'
      end
    rescue Errno::EWOULDBLOCK, Errno::EAGAIN, IO::TimeoutError
      log 'Client connection timed out'
      begin
        client.close
      rescue
        nil
      end
    end

    # Read data from client with timeout to prevent hanging
    # @param client [TCPSocket] client connection
    # @param timeout [Float] timeout in seconds
    # @return [String, nil] received data or nil on timeout
    def read_with_timeout(client, timeout)
      ready = IO.select([client], nil, nil, timeout)
      return nil unless ready

      # Try to read available data
      data = ''
      begin
        while (chunk = client.read_nonblock(1024))
          data += chunk
          # Check if we have a complete JSON object (simple heuristic)
          if data.include?("\n") || (data.count('{').positive? && data.count('{') == data.count('}'))
            break
          end
        end
      rescue IO::WaitReadable
        # No more data available right now
      rescue EOFError
        # Client disconnected
        return nil if data.empty?
      end

      data.empty? ? nil : data
    end

    # Handle JSON-RPC request
    # @param request [Hash] parsed JSON-RPC request
    # @return [Hash] JSON-RPC response
    def handle_jsonrpc_request(request)
      log "Handling JSON-RPC request: #{request.inspect}"

      # Handle legacy command format for backwards compatibility
      return handle_legacy_command(request) if request['command']

      # Handle standard JSON-RPC methods
      case request['method']
      when 'tools/call'
        handle_tool_call(request)
      when 'ping'
        handle_ping(request)
      when 'resources/list'
        handle_resources_list(request)
      else
        Utils.create_error_response(request, "Method not found: #{request['method']}", -32_601)
      end
    end

    # Handle legacy command format
    # @param request [Hash] legacy request format
    # @return [Hash] JSON-RPC response
    def handle_legacy_command(request)
      tool_request = {
        'method' => 'tools/call',
        'params' => {
          'name' => request['command'],
          'arguments' => request['parameters']
        },
        'jsonrpc' => request['jsonrpc'] || '2.0',
        'id' => request['id']
      }
      log "Converting to tool request: #{tool_request.inspect}"
      handle_tool_call(tool_request)
    end

    # Handle ping request
    # @param request [Hash] JSON-RPC request
    # @return [Hash] JSON-RPC response
    def handle_ping(request)
      Utils.create_success_response(request, {
                                      status: 'ok',
                                      version: VERSION,
                                      message: 'Supex server is running'
                                    })
    end

    # Handle resources list request
    # @param request [Hash] JSON-RPC request
    # @return [Hash] JSON-RPC response
    def handle_resources_list(request)
      resources = list_resources
      Utils.create_success_response(request, {
                                      resources: resources,
                                      success: true
                                    })
    end

    # Handle tool call request
    # @param request [Hash] JSON-RPC request
    # @return [Hash] JSON-RPC response
    def handle_tool_call(request)
      log "Handling tool call: #{request.inspect}"
      tool_name = request['params']['name']
      args = request['params']['arguments']

      begin
        result = execute_tool(tool_name, args)
        log "Tool call result: #{result.inspect}"
        Utils.create_success_response(request, result)
      rescue StandardError => e
        log "Tool call error: #{e.message}"
        log e.backtrace.join("\n")
        Utils.create_error_response(request, e.message)
      end
    end

    # Execute tool by name
    # @param tool_name [String] name of tool to execute
    # @param args [Hash] tool arguments
    # @return [Hash] tool execution result
    def execute_tool(tool_name, args)
      case tool_name
      when 'ping'
        ping
      when 'export_scene'
        Export.export_scene(args)
      when 'eval_ruby'
        eval_ruby(args)
      when 'reload_extension'
        reload_extension
      when 'console_capture_status'
        console_capture_status
      when 'eval_ruby_file'
        eval_ruby_file(args)
      # Introspection tools
      when 'get_model_info'
        get_model_info
      when 'list_entities'
        list_entities(args)
      when 'get_selection'
        get_selection
      when 'get_layers'
        get_layers
      when 'get_materials'
        get_materials
      when 'get_camera_info'
        get_camera_info
      when 'take_screenshot'
        take_screenshot(args)
      when 'open_model'
        open_model(args)
      when 'save_model'
        save_model(args)
      else
        raise "Unknown tool: #{tool_name}"
      end
    end

    # List available resources (entities in the model)
    # @return [Array<Hash>] array of resource information
    def list_resources
      model = Sketchup.active_model
      return [] unless model

      model.entities.map do |entity|
        {
          id: entity.entityID,
          type: entity.typename.downcase,
          bounds: entity.respond_to?(:bounds) ? Utils.bounds_to_hash(entity.bounds) : nil
        }
      end
    end

    # Evaluate Ruby code in SketchUp context
    # @param params [Hash] parameters containing Ruby code
    # @return [Hash] evaluation result
    def eval_ruby(params)
      log "Evaluating Ruby code (#{params['code'].length} chars)"

      begin
        # Add marker for Ruby code execution
        @console_capture&.add_marker('EVAL_RUBY START')

        # Create safe binding for evaluation
        binding = TOPLEVEL_BINDING.dup
        result = eval(params['code'], binding)

        @console_capture&.add_marker('EVAL_RUBY END')

        {
          success: true,
          result: result.to_s
        }
      rescue StandardError => e
        @console_capture&.add_marker("EVAL_RUBY ERROR: #{e.message}")
        log "Ruby eval error: #{e.message}"
        raise "Ruby evaluation error: #{e.message}"
      end
    end

    # Ping tool for connection health checking
    # @return [Hash] ping response with status information
    def ping
      {
        success: true,
        status: 'connected',
        message: 'SketchUp extension is running',
        version: SupexRuntime::VERSION,
        sketchup_version: Sketchup.version
      }
    end

    # Reload the extension during development
    # @return [Hash] reload operation result
    def reload_extension
      log 'Reloading extension via MCP...'

      result = Main.reload_extension

      {
        success: result,
        message: result ? 'Extension reloaded successfully' : 'Extension reload failed'
      }
    end

    # Get console capture status and information
    # @return [Hash] console capture status
    def console_capture_status
      if @console_capture
        {
          success: true,
          capturing: @console_capture.capturing?,
          log_file: @console_capture.log_file_path,
          message: @console_capture.capturing? ? 'Console capture is active' : 'Console capture is inactive'
        }
      else
        {
          success: false,
          capturing: false,
          log_file: nil,
          message: 'Console capture not initialized'
        }
      end
    end

    # Evaluate Ruby code from a file in SketchUp context
    # @param params [Hash] parameters containing file path
    # @return [Hash] evaluation result with file context
    def eval_ruby_file(params)
      file_path = params['file_path']

      raise "Ruby file not found: #{file_path}" unless File.exist?(file_path)

      log "Evaluating Ruby file: #{File.basename(file_path)}"

      begin
        # Add enhanced marker for file evaluation
        @console_capture&.add_marker("EVAL_RUBY_FILE START: #{file_path}")

        # Read and evaluate file with proper file context
        ruby_code = File.read(file_path)
        result = eval(ruby_code, TOPLEVEL_BINDING, file_path, 1)

        @console_capture&.add_marker("EVAL_RUBY_FILE END: #{file_path}")

        {
          success: true,
          result: result.to_s,
          file_path: file_path,
          file_name: File.basename(file_path)
        }
      rescue StandardError => e
        @console_capture&.add_marker("EVAL_RUBY_FILE ERROR: #{e.message}")
        log "Ruby file eval error: #{e.message}"

        # Enhanced error reporting with file context
        error_msg = "Error in #{File.basename(file_path)}: #{e.message}"
        error_msg += "\nFile: #{file_path}"
        error_msg += "\nLine: #{e.backtrace&.first&.split(':')&.[](1)}" if e.backtrace

        raise error_msg
      end
    end

    # Get basic information about the current SketchUp model
    # @return [Hash] model statistics and metadata
    def get_model_info
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
        # Get units setting
        units_options = model.options['UnitsOptions']
        length_unit = units_options['LengthUnit']
        units_map = {
          0 => 'inches',
          1 => 'feet',
          2 => 'millimeters',
          3 => 'centimeters',
          4 => 'meters'
        }

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
      rescue StandardError => e
        log "Error getting model info: #{e.message}"
        raise "Failed to get model info: #{e.message}"
      end
    end

    # List entities in the model
    # @param params [Hash] parameters with optional entity_type filter
    # @return [Hash] list of entities
    def list_entities(params)
      model = Sketchup.active_model
      entity_type = params['entity_type'] || 'all'

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
        entities = case entity_type
                   when 'faces'
                     model.entities.grep(Sketchup::Face)
                   when 'edges'
                     model.entities.grep(Sketchup::Edge)
                   when 'groups'
                     model.entities.grep(Sketchup::Group)
                   when 'components'
                     model.entities.grep(Sketchup::ComponentInstance)
                   else
                     model.entities.to_a
                   end

        entities_data = entities.map do |entity|
          data = {
            type: entity.typename,
            entity_id: entity.entityID
          }

          # Add type-specific properties
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

        {
          success: true,
          entity_type: entity_type,
          count: entities_data.length,
          entities: entities_data
        }
      rescue StandardError => e
        log "Error listing entities: #{e.message}"
        raise "Failed to list entities: #{e.message}"
      end
    end

    # Get currently selected entities
    # @return [Hash] selection information
    def get_selection
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
        selection = model.selection

        entities_data = selection.map do |entity|
          data = {
            type: entity.typename,
            entity_id: entity.entityID
          }

          # Add type-specific details
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

        {
          success: true,
          count: selection.count,
          entities: entities_data
        }
      rescue StandardError => e
        log "Error getting selection: #{e.message}"
        raise "Failed to get selection: #{e.message}"
      end
    end

    # Get list of layers (tags) in the model
    # @return [Hash] layers information
    def get_layers
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
        layers_data = model.layers.map do |layer|
          {
            name: layer.name,
            visible: layer.visible?,
            page_behavior: layer.page_behavior
          }
        end

        {
          success: true,
          count: layers_data.length,
          layers: layers_data
        }
      rescue StandardError => e
        log "Error getting layers: #{e.message}"
        raise "Failed to get layers: #{e.message}"
      end
    end

    # Get list of materials in the model
    # @return [Hash] materials information
    def get_materials
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
        materials_data = model.materials.map do |material|
          data = {
            name: material.name,
            display_name: material.display_name
          }

          # Add color if available
          if material.color
            data[:color] = {
              red: material.color.red,
              green: material.color.green,
              blue: material.color.blue,
              alpha: material.alpha
            }
          end

          # Check for texture
          data[:textured] = material.texture ? true : false

          data
        end

        {
          success: true,
          count: materials_data.length,
          materials: materials_data
        }
      rescue StandardError => e
        log "Error getting materials: #{e.message}"
        raise "Failed to get materials: #{e.message}"
      end
    end

    # Get current camera information
    # @return [Hash] camera settings
    def get_camera_info
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
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
      rescue StandardError => e
        log "Error getting camera info: #{e.message}"
        raise "Failed to get camera info: #{e.message}"
      end
    end

    # Take a screenshot of the current view and save to disk
    # @param params [Hash] parameters with width, height, transparent, output_path
    # @return [Hash] screenshot result with file path (not image data)
    def take_screenshot(params)
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      width = params['width'] || 1920
      height = params['height'] || 1080
      transparent = params['transparent'] || false
      output_path = params['output_path']

      begin
        view = model.active_view

        # Determine target location
        if output_path
          screenshot_path = File.expand_path(output_path)
          # Ensure parent directory exists
          FileUtils.mkdir_p(File.dirname(screenshot_path))
        else
          # Default: save to .tmp/screenshots/ in supex repo with timestamp
          screenshots_dir = File.join(File.dirname(__FILE__), '..', '..', '..', '..', '.tmp',
                                      'screenshots')
          FileUtils.mkdir_p(screenshots_dir)
          timestamp = Time.now.strftime('%Y%m%d-%H%M%S')
          screenshot_path = File.join(screenshots_dir, "screenshot-#{timestamp}.png")
        end

        # Write screenshot to disk
        options = {
          filename: screenshot_path,
          width: width,
          height: height,
          antialias: true,
          compression: 0.9,
          transparent: transparent
        }

        view.write_image(options)

        # Return only the file path (not image data!)
        {
          success: true,
          file_path: screenshot_path,
          file_name: File.basename(screenshot_path),
          width: width,
          height: height,
          format: 'png',
          message: "Screenshot saved to #{screenshot_path}. Use Read tool to view if needed."
        }
      rescue StandardError => e
        log "Error taking screenshot: #{e.message}"
        log e.backtrace.join("\n")
        raise "Failed to take screenshot: #{e.message}"
      end
    end

    # Open a SketchUp model file
    # @param params [Hash] parameters with file path
    # @return [Hash] open operation result
    def open_model(params)
      file_path = params['path']

      unless file_path
        return {
          success: false,
          error: 'No file path provided'
        }
      end

      unless File.exist?(file_path)
        return {
          success: false,
          error: "File not found: #{file_path}"
        }
      end

      begin
        Sketchup.open_file(file_path)

        # Get info about newly opened model
        model = Sketchup.active_model

        {
          success: true,
          file_path: file_path,
          file_name: File.basename(file_path),
          title: model.title
        }
      rescue StandardError => e
        log "Error opening model: #{e.message}"
        raise "Failed to open model: #{e.message}"
      end
    end

    # Save the current model
    # @param params [Hash] parameters with optional save path
    # @return [Hash] save operation result
    def save_model(params)
      model = Sketchup.active_model

      unless model
        return {
          success: false,
          error: 'No active model'
        }
      end

      begin
        if params['path']
          # Save to specific path
          model.save(params['path'])
          saved_path = params['path']
        else
          # Save to current path (or prompt if untitled)
          model.save
          saved_path = model.path
        end

        {
          success: true,
          file_path: saved_path,
          file_name: File.basename(saved_path),
          title: model.title
        }
      rescue StandardError => e
        log "Error saving model: #{e.message}"
        raise "Failed to save model: #{e.message}"
      end
    end

    # Send error response to client
    # @param client [TCPSocket] client connection
    # @param message [String] error message
    # @param code [Integer] error code
    # @param request_id [Object] request ID
    def send_error_response(client, message, code, request_id)
      error_response = {
        jsonrpc: '2.0',
        error: { code: code, message: message },
        id: request_id
      }.to_json + "\n"

      client.write(error_response)
      client.flush
      # Give the client time to read the error response
      sleep(0.25)
    end
  end
end
