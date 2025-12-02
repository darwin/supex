# frozen_string_literal: true

require 'socket'
require 'stringio'
require 'fileutils'
require 'json'

require_relative 'version'
require_relative 'utils'

module SupexRuntime
  # JSON-RPC REPL Server for interactive Ruby development in SketchUp
  # Evaluates code in TOPLEVEL_BINDING (same as SketchUp's internal console)
  # Accessible via TCP socket on a separate port from MCP
  #
  # Protocol: JSON-RPC 2.0 with hello handshake
  # - hello: Client identification with PID for session management
  # - eval: Execute Ruby code and return result
  #
  # Architecture: Non-blocking with persistent client connections
  # - Timer checks for new connections and pending data
  # - Multiple clients can connect simultaneously
  # - Each client has its own session directory for snippets
  class REPLServer
    DEFAULT_REPL_PORT = 4433
    DEFAULT_REPL_HOST = '127.0.0.1'
    REQUEST_CHECK_INTERVAL = 0.1
    SNIPPETS_DIR = File.expand_path('../../../.tmp/repl', __dir__)

    # Connection context for scoped client state
    ClientConnection = Struct.new(:socket, :client_info, :session_dir, :snippet_counter, keyword_init: true) do
      def identified?
        !client_info.nil?
      end
    end

    attr_reader :port, :host

    def initialize(port: DEFAULT_REPL_PORT, host: DEFAULT_REPL_HOST)
      @port = Integer(ENV.fetch('SUPEX_REPL_PORT', port))
      @host = host
      @server = nil
      @running = false
      @timer_id = nil
      @verbose = ENV['SUPEX_VERBOSE'] == '1'
      @clients = [] # Active client connections
    end

    # Start the REPL server
    def start
      return true if @running

      begin
        log "Starting REPL server on #{@host}:#{@port}..."

        @server = TCPServer.new(@host, @port)
        @running = true
        @clients = []
        start_request_handler

        log 'REPL server started and listening'
        true
      rescue StandardError => e
        log "Error starting REPL server: #{e.message}"
        log e.backtrace.join("\n")
        stop
        false
      end
    end

    # Stop the REPL server
    def stop
      log 'Stopping REPL server...'
      @running = false

      stop_timer
      close_all_clients
      close_server

      log 'REPL server stopped'
    end

    # Check if server is running
    def running?
      @running
    end

    private

    # Start request handler timer
    def start_request_handler
      @timer_id = UI.start_timer(REQUEST_CHECK_INTERVAL, true) do
        handle_tick if @running
      rescue StandardError => e
        log "Timer handler error: #{e.message}"
      end
    end

    # Stop the timer
    def stop_timer
      return unless @timer_id

      UI.stop_timer(@timer_id)
      @timer_id = nil
    end

    # Close all client connections
    def close_all_clients
      @clients.each do |client|
        log_client_closed(client)
        client.socket.close rescue nil
      end
      @clients.clear
    end

    # Close the server socket
    def close_server
      return unless @server

      @server.close
      @server = nil
    end

    # Timer tick - accept new connections and process pending data
    def handle_tick
      return unless @server && @running

      accept_new_connections
      process_client_data
    end

    # Accept any pending new connections (non-blocking)
    def accept_new_connections
      loop do
        socket = @server.accept_nonblock
        client = ClientConnection.new(
          socket: socket,
          client_info: nil,
          session_dir: nil,
          snippet_counter: 0
        )
        @clients << client
        log_verbose 'New client connected'
      rescue Errno::EWOULDBLOCK, Errno::EAGAIN
        break # No more pending connections
      rescue StandardError => e
        log "Error accepting connection: #{e.message}"
        break
      end
    end

    # Process data from all connected clients (non-blocking)
    def process_client_data
      @clients.delete_if do |client|
        process_client(client) == :disconnect
      end
    end

    # Process single client - returns :disconnect if client should be removed
    # @param client [ClientConnection] client to process
    # @return [Symbol, nil] :disconnect to remove client, nil to keep
    def process_client(client)
      # Check if data is available (non-blocking)
      # rubocop:disable Lint/IncompatibleIoSelectWithFiberScheduler
      ready = IO.select([client.socket], nil, nil, 0)
      # rubocop:enable Lint/IncompatibleIoSelectWithFiberScheduler
      return nil unless ready

      # Try to read a line
      line = client.socket.gets
      unless line
        log_client_closed(client)
        client.socket.close rescue nil
        return :disconnect
      end

      # Process the request
      process_request(client, line.strip)
      nil
    rescue IOError, Errno::ECONNRESET, Errno::EPIPE => e
      log_verbose "Client disconnected: #{e.message}"
      log_client_closed(client)
      client.socket.close rescue nil
      :disconnect
    rescue StandardError => e
      log "Error processing client: #{e.message}"
      client.socket.close rescue nil
      :disconnect
    end

    # Process a JSON-RPC request from client
    # @param client [ClientConnection] client connection
    # @param data [String] request data
    def process_request(client, data)
      request = JSON.parse(data)
      log_verbose "REPL request: #{request['method']}"

      response = handle_jsonrpc_request(request, client)
      client.socket.write("#{response.to_json}\n")
      client.socket.flush
    rescue JSON::ParserError => e
      send_error_response(client.socket, "Parse error: #{e.message}", -32_700, nil)
    end

    # Handle JSON-RPC request
    # @param request [Hash] parsed JSON-RPC request
    # @param client [ClientConnection] client connection
    # @return [Hash] JSON-RPC response
    def handle_jsonrpc_request(request, client)
      case request['method']
      when 'hello'
        handle_hello(request, client)
      when 'eval'
        return require_hello_error(request) unless client.identified?

        handle_eval(request, client)
      else
        error_response(request, "Method not found: #{request['method']}", -32_601)
      end
    end

    # Handle hello handshake request
    # @param request [Hash] JSON-RPC request
    # @param client [ClientConnection] client connection
    # @return [Hash] JSON-RPC response
    def handle_hello(request, client)
      params = request['params'] || {}
      pid = params['pid']
      name = params['name'] || 'unknown'

      # Create session directory
      timestamp = Time.now.strftime('%y%m%d-%H%M%S')
      session_name = "s#{timestamp}-#{pid || Process.pid}"
      client.session_dir = File.join(SNIPPETS_DIR, session_name)
      FileUtils.mkdir_p(client.session_dir)

      client.client_info = params

      log "Client connected: #{name} [PID:#{pid}] -> #{session_name}"

      success_response(request, {
                         success: true,
                         session: session_name,
                         server: { name: 'supex-repl', version: VERSION }
                       })
    end

    # Handle eval request
    # @param request [Hash] JSON-RPC request
    # @param client [ClientConnection] client connection
    # @return [Hash] JSON-RPC response
    def handle_eval(request, client)
      code = request.dig('params', 'code')
      return error_response(request, 'Missing code parameter', -32_602) unless code

      client.snippet_counter += 1
      snippet_path = File.join(client.session_dir, format('%04d.rb', client.snippet_counter))
      File.write(snippet_path, code)

      log_verbose "Evaluating snippet #{client.snippet_counter}"

      output = eval_code_with_capture(code, snippet_path)
      success_response(request, { output: output, success: true })
    end

    # Return error for unidentified clients
    # @param request [Hash] JSON-RPC request
    # @return [Hash] JSON-RPC error response
    def require_hello_error(request)
      error_response(request, "Client must send 'hello' first", -32_600)
    end

    # Evaluate code in TOPLEVEL_BINDING with stdout/stderr capture
    # @param code [String] Ruby code to evaluate
    # @param snippet_path [String] path to snippet file for stack traces
    # @return [String] evaluation output
    def eval_code_with_capture(code, snippet_path)
      output = StringIO.new

      with_captured_output(output) do
        # rubocop:disable Security/Eval
        result = eval(code, TOPLEVEL_BINDING, snippet_path, 1)
        # rubocop:enable Security/Eval
        output.puts "=> #{result.inspect}"
      rescue Exception => e # rubocop:disable Lint/RescueException
        output.puts "#<#{e.class}: #{e.message}>"
        filtered = filter_backtrace(e.backtrace)
        output.puts filtered.first(5).join("\n") if filtered.any?
      end

      output.rewind
      output.read
    end

    # Filter internal frames from backtrace for cleaner output
    # @param backtrace [Array<String>, nil] original backtrace
    # @return [Array<String>] filtered backtrace
    def filter_backtrace(backtrace)
      return [] unless backtrace

      backtrace.reject do |line|
        line.include?('repl_server.rb') ||
          line.include?("in `eval'") ||
          line.include?('supex_runtime/')
      end
    end

    # Capture stdout/stderr during block execution
    # @param output [StringIO] output stream to capture to
    def with_captured_output(output)
      prev_stdout = $stdout
      prev_stderr = $stderr
      $stdout = output
      $stderr = output
      yield
    ensure
      $stdout = prev_stdout
      $stderr = prev_stderr
    end

    # Create JSON-RPC success response
    # @param request [Hash] original request
    # @param result [Object] result data
    # @return [Hash] JSON-RPC response
    def success_response(request, result)
      { jsonrpc: '2.0', id: request['id'], result: result }
    end

    # Create JSON-RPC error response
    # @param request [Hash] original request
    # @param message [String] error message
    # @param code [Integer] error code
    # @return [Hash] JSON-RPC response
    def error_response(request, message, code)
      { jsonrpc: '2.0', id: request['id'], error: { code: code, message: message } }
    end

    # Send error response directly to connection
    # @param socket [TCPSocket] client socket
    # @param message [String] error message
    # @param code [Integer] error code
    # @param request_id [Object] request ID
    def send_error_response(socket, message, code, request_id)
      response = { jsonrpc: '2.0', id: request_id, error: { code: code, message: message } }
      socket.write("#{response.to_json}\n")
      socket.flush
    end

    # Log client closed message
    # @param client [ClientConnection] client connection
    def log_client_closed(client)
      if client.identified?
        info = client.client_info
        log "Client closed: #{info['name']} [PID:#{info['pid']}]"
      else
        log_verbose 'Client closed (unidentified)'
      end
    end

    # Log message to SketchUp console
    def log(message)
      Utils.console_write("Supex: REPL> #{message}")
      $stdout.flush
    end

    # Log message only when SUPEX_VERBOSE=1
    def log_verbose(message)
      return unless @verbose

      log(message)
    end
  end
end
