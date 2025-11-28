# frozen_string_literal: true

require 'json'
require 'socket'
require 'fileutils'
require_relative 'version'
require_relative 'utils'
require_relative 'export'
require_relative 'console_capture'
require_relative 'tools'

module SupexRuntime
  # TCP server for handling JSON-RPC requests from the Python MCP server
  # rubocop:disable Metrics/ClassLength
  class Server
    include Tools

    DEFAULT_PORT = 9876
    DEFAULT_HOST = '127.0.0.1'
    MAX_MESSAGE_SIZE = 1_048_576 # 1 MB limit to prevent DoS
    REQUEST_CHECK_INTERVAL = ENV['SUPEX_CHECK_INTERVAL']&.to_f || 0.25
    RESPONSE_DELAY = ENV['SUPEX_RESPONSE_DELAY']&.to_f || 0

    # Connection context for scoped client state (thread-safe pattern)
    ConnectionContext = Struct.new(:client_info, keyword_init: true) do
      def identified?
        !client_info.nil?
      end
    end

    def initialize(port: DEFAULT_PORT, host: DEFAULT_HOST)
      @port = port
      @host = host
      @server = nil
      @running = false
      @timer_id = nil
      @console_capture = nil
      @verbose = ENV['SUPEX_VERBOSE'] == '1'

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
      tmp_dir = File.join(File.dirname(__FILE__), '..', '..', '..', '.tmp')
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
    end

    # Stop console output capture
    def stop_console_capture
      return unless @console_capture

      @console_capture.stop_capture
    end

    # Log message to SketchUp console
    # @param message [String] message to log
    def log(message)
      Utils.console_write("Supex: #{message}")
      $stdout.flush
    end

    # Log message only when SUPEX_VERBOSE=1
    # @param message [String] message to log
    def log_verbose(message)
      return unless @verbose

      log(message)
    end

    # Format arguments hash for user-friendly logging
    # @param args [Hash] tool arguments
    # @return [String] formatted arguments
    def format_args(args)
      return '' if args.nil? || args.empty?

      args.map do |key, value|
        formatted = value.is_a?(String) && value.length > 200 ? "\"#{value[0..197]}...\"" : value.inspect
        "#{key}: #{formatted}"
      end.join(', ')
    end

    # Start the request handler timer
    def start_request_handler
      # Configurable interval via SUPEX_CHECK_INTERVAL (default 0.25s)
      @timer_id = UI.start_timer(REQUEST_CHECK_INTERVAL, true) do
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
        # rubocop:disable Lint/IncompatibleIoSelectWithFiberScheduler
        ready = IO.select([@server], nil, nil, 0)
        # rubocop:enable Lint/IncompatibleIoSelectWithFiberScheduler
        return unless ready

        log 'Connection waiting...'

        # Accept connection with timeout protection
        begin
          client = @server.accept_nonblock
          log_verbose 'Client socket accepted'
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
    # Supports multiple requests per connection with mandatory hello handshake
    # @param client [TCPSocket] client connection
    def process_client_request(client)
      # Set a reasonable timeout to prevent hanging
      client.setsockopt(Socket::SOL_SOCKET, Socket::SO_RCVTIMEO, [5, 0].pack('L!L!'))

      # Create connection-scoped context for client state
      context = ConnectionContext.new(client_info: nil)

      # Process requests in a loop until client disconnects or error
      loop do
        break unless process_single_request(client, context)
      end
    rescue Errno::EWOULDBLOCK, Errno::EAGAIN, IO::TimeoutError
      log 'Client connection timed out'
    ensure
      log_client_closed(context)
      begin
        client.close
      rescue StandardError
        nil
      end
    end

    # Process a single request from client
    # @param client [TCPSocket] client connection
    # @param context [ConnectionContext] connection-scoped state
    # @return [Boolean] true to continue processing, false to close connection
    def process_single_request(client, context)
      data = read_with_timeout(client, 5.0)
      log_verbose "Raw data: #{data.inspect}"

      return false unless data && !data.empty?

      begin
        json_data = data.strip
        request = JSON.parse(json_data)
        log_verbose "Parsed request: #{request.inspect}"

        response = handle_jsonrpc_request(request, context)
        send_response(client, response)

        # Continue loop only for hello requests, close after other requests
        request['method'] == 'hello'
      rescue JSON::ParserError => e
        log "JSON parse error: #{e.message}"
        log "Raw data was: #{data.inspect}"
        send_error_response(client, 'Parse error', -32_700, nil)
        false
      rescue StandardError => e
        log "Request error: #{e.message}"
        log e.backtrace.join("\n")
        send_error_response(client, e.message, -32_603, request&.dig('id'))
        false
      end
    end

    # Send response to client
    # @param client [TCPSocket] client connection
    # @param response [Hash] response to send
    def send_response(client, response)
      response_json = "#{response.to_json}\n"
      log_verbose "Sending response: #{response_json.strip}"
      client.write(response_json)
      client.flush
      log 'Response sent'
      sleep(RESPONSE_DELAY) if RESPONSE_DELAY.positive?
    end

    # Log client closed message with identification if available
    # @param context [ConnectionContext] connection-scoped state
    def log_client_closed(context)
      if context.identified?
        info = context.client_info
        log "Client closed: #{info[:name]}/#{info[:version]} [PID:#{info[:pid]}]"
      else
        log_verbose 'Client closed (unidentified)'
      end
    end

    # Read data from client with timeout to prevent hanging
    # @param client [TCPSocket] client connection
    # @param timeout [Float] timeout in seconds
    # @return [String, nil] received data or nil on timeout
    def read_with_timeout(client, timeout)
      # rubocop:disable Lint/IncompatibleIoSelectWithFiberScheduler
      ready = IO.select([client], nil, nil, timeout)
      # rubocop:enable Lint/IncompatibleIoSelectWithFiberScheduler
      return nil unless ready

      read_available_data(client)
    end

    # Read all available data from client socket
    # @param client [TCPSocket] client connection
    # @return [String, nil] received data or nil if empty
    def read_available_data(client)
      data = String.new
      loop do
        chunk = client.read_nonblock(1024)
        data << chunk
        raise "Message exceeds maximum size (#{MAX_MESSAGE_SIZE} bytes)" if data.bytesize > MAX_MESSAGE_SIZE
        break if complete_json?(data)
      end
      data.empty? ? nil : data
    rescue IO::WaitReadable
      data.empty? ? nil : data
    rescue EOFError
      data.empty? ? nil : data
    end

    # Check if data contains a complete JSON object
    # @param data [String] data to check
    # @return [Boolean] true if complete
    def complete_json?(data)
      data.include?("\n") || (data.count('{').positive? && data.count('{') == data.count('}'))
    end

    # Handle JSON-RPC request
    # @param request [Hash] parsed JSON-RPC request
    # @param context [ConnectionContext] connection-scoped state
    # @return [Hash] JSON-RPC response
    def handle_jsonrpc_request(request, context)
      log_verbose "Handling JSON-RPC request: #{request.inspect}"

      # Handle hello method first (no identification required)
      return handle_hello(request, context) if request['method'] == 'hello'

      # Require client identification for all other methods
      return require_identification_error(request) unless context.identified?

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

    # Handle hello handshake request
    # @param request [Hash] JSON-RPC request with client identification
    # @param context [ConnectionContext] connection-scoped state
    # @return [Hash] JSON-RPC response
    def handle_hello(request, context)
      params = request['params'] || {}

      # Validate required fields
      name = params['name']
      version = params['version']
      agent = params['agent']
      pid = params['pid']

      unless name && version && agent && pid
        return Utils.create_error_response(
          request,
          'Missing required params: name, version, agent, pid',
          -32_600
        )
      end

      # Store client info in connection context
      context.client_info = {
        name: name,
        version: version,
        agent: agent,
        pid: pid
      }

      log "Client connected: #{name}/#{version} [PID:#{pid}] (agent: #{agent})"

      Utils.create_success_response(request, {
                                      success: true,
                                      message: 'Client identified',
                                      server: {
                                        name: 'supex-runtime',
                                        version: VERSION
                                      }
                                    })
    end

    # Return error for unidentified clients
    # @param request [Hash] JSON-RPC request
    # @return [Hash] JSON-RPC error response
    def require_identification_error(request)
      Utils.create_error_response(
        request,
        "Client must identify with 'hello' method first",
        -32_600,
        { hint: 'Send hello method with params: name, version, agent, pid' }
      )
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
      log_verbose "Handling tool call: #{request.inspect}"
      tool_name = request['params']['name']
      args = request['params']['arguments']
      log "Calling #{tool_name}(#{format_args(args)})"

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
      execute_core_tool(tool_name, args) || execute_introspection_tool(tool_name, args) ||
        (raise "Unknown tool: #{tool_name}")
    end

    # Execute core tools (eval, export, etc.)
    # @return [Hash, nil] result or nil if not a core tool
    def execute_core_tool(tool_name, args)
      case tool_name
      when 'ping' then ping
      when 'export_scene' then Export.export_scene(args)
      when 'eval_ruby' then eval_ruby(args)
      when 'reload_extension' then reload_extension
      when 'console_capture_status' then console_capture_status
      when 'eval_ruby_file' then eval_ruby_file(args)
      end
    end

    # Execute introspection and file tools
    # @return [Hash, nil] result or nil if not an introspection tool
    def execute_introspection_tool(tool_name, args)
      case tool_name
      when 'get_model_info' then model_info
      when 'list_entities' then list_entities(args)
      when 'get_selection' then selection_info
      when 'get_layers' then layers_info
      when 'get_materials' then materials_info
      when 'get_camera_info' then camera_info
      when 'take_screenshot' then take_screenshot(args)
      when 'open_model' then open_model(args)
      when 'save_model' then save_model(args)
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
        @console_capture&.add_marker('EVAL_RUBY START')
        binding = TOPLEVEL_BINDING.dup
        # rubocop:disable Security/Eval
        result = eval(params['code'], binding)
        # rubocop:enable Security/Eval
        @console_capture&.add_marker('EVAL_RUBY END')

        { success: true, result: result.to_s }
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
        status_msg = @console_capture.capturing? ? 'Console capture is active' : 'Console capture is inactive'
        {
          success: true,
          capturing: @console_capture.capturing?,
          log_file: @console_capture.log_file_path,
          message: status_msg
        }
      else
        { success: false, capturing: false, log_file: nil,
          message: 'Console capture not initialized' }
      end
    end

    # Evaluate Ruby code from a file in SketchUp context
    # @param params [Hash] parameters containing file path
    # @return [Hash] evaluation result with file context
    def eval_ruby_file(params)
      file_path = params['file_path']
      raise "Ruby file not found: #{file_path}" unless File.exist?(file_path)

      log "Evaluating Ruby file: #{File.basename(file_path)}"
      execute_ruby_file(file_path)
    end

    # Execute Ruby file and return result
    # @param file_path [String] path to Ruby file
    # @return [Hash] execution result
    def execute_ruby_file(file_path)
      @console_capture&.add_marker("EVAL_RUBY_FILE START: #{file_path}")
      ruby_code = File.read(file_path)
      # rubocop:disable Security/Eval
      result = eval(ruby_code, TOPLEVEL_BINDING, file_path, 1)
      # rubocop:enable Security/Eval
      @console_capture&.add_marker("EVAL_RUBY_FILE END: #{file_path}")

      { success: true, result: result.to_s, file_path: file_path,
        file_name: File.basename(file_path) }
    rescue StandardError => e
      handle_ruby_file_error(file_path, e)
    end

    # Handle error from Ruby file evaluation
    # @param file_path [String] path to Ruby file
    # @param error [StandardError] the error that occurred
    def handle_ruby_file_error(file_path, error)
      @console_capture&.add_marker("EVAL_RUBY_FILE ERROR: #{error.message}")
      log "Ruby file eval error: #{error.message}"

      error_msg = "Error in #{File.basename(file_path)}: #{error.message}\nFile: #{file_path}"
      error_msg += "\nLine: #{extract_line_number(error)}" if error.backtrace
      raise error_msg
    end

    # Extract line number from error backtrace
    # @param error [StandardError] the error
    # @return [String, nil] line number or nil
    def extract_line_number(error)
      return nil unless error.backtrace&.first

      parts = error.backtrace.first.split(':')
      parts[1]
    end

    # Send error response to client
    # @param client [TCPSocket] client connection
    # @param message [String] error message
    # @param code [Integer] error code
    # @param request_id [Object] request ID
    def send_error_response(client, message, code, request_id)
      error_response = { jsonrpc: '2.0', error: { code: code, message: message }, id: request_id }
      client.write("#{error_response.to_json}\n")
      client.flush
      sleep(RESPONSE_DELAY) if RESPONSE_DELAY.positive?
    end
  end
  # rubocop:enable Metrics/ClassLength
end
