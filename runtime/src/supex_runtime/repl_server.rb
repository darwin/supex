# frozen_string_literal: true

require 'socket'
require 'stringio'

require_relative 'version'
require_relative 'utils'

module SupexRuntime
  # Simple REPL Server for interactive Ruby development in SketchUp
  # Evaluates code in TOPLEVEL_BINDING (same as SketchUp's internal console)
  # Accessible via TCP socket on a separate port from MCP
  class REPLServer
    DEFAULT_REPL_PORT = 4433
    DEFAULT_REPL_HOST = '127.0.0.1'
    REQUEST_CHECK_INTERVAL = 0.1

    attr_reader :port, :host

    def initialize(port: DEFAULT_REPL_PORT, host: DEFAULT_REPL_HOST)
      @port = Integer(ENV.fetch('SUPEX_REPL_PORT', port))
      @host = host
      @server = nil
      @running = false
      @timer_id = nil
      @verbose = ENV['SUPEX_VERBOSE'] == '1'
    end

    # Start the REPL server
    def start
      return true if @running

      begin
        log "Starting REPL server on #{@host}:#{@port}..."

        @server = TCPServer.new(@host, @port)
        @running = true
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
        handle_requests if @running
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

    # Close the server socket
    def close_server
      return unless @server

      @server.close
      @server = nil
    end

    # Handle incoming REPL requests
    def handle_requests
      return unless @server && @running

      begin
        connection = @server.accept_nonblock
        process_repl_request(connection)
      rescue Errno::EWOULDBLOCK, Errno::EAGAIN
        # No connection available, this is normal
        nil
      rescue StandardError => e
        log "REPL request error: #{e.message}"
      end
    end

    # Process a single REPL request
    # @param connection [TCPSocket] client connection
    def process_repl_request(connection)
      message = connection.read # blocking read

      if message && !message.empty?
        log_verbose "REPL received: #{message.chomp}"
        result = eval_code(message)
        connection.write(result)
        connection.close_write
      end

      connection.close
    rescue StandardError => e
      log "REPL processing error: #{e.message}"
      begin
        connection.write("Error: #{e.message}\n")
        connection.close
      rescue StandardError
        nil
      end
    end

    # Evaluate code in TOPLEVEL_BINDING (like SketchUp console)
    # @param code [String] Ruby code to evaluate
    # @return [String] evaluation result
    def eval_code(code)
      output = StringIO.new

      with_captured_output(output) do
        begin
          # rubocop:disable Security/Eval
          result = eval(code, TOPLEVEL_BINDING)
          # rubocop:enable Security/Eval
          output.puts "=> #{result.inspect}"
        rescue Exception => e # rubocop:disable Lint/RescueException
          output.puts "#<#{e.class}: #{e.message}>"
          output.puts e.backtrace.first(5).join("\n") if e.backtrace
        end
      end

      output.rewind
      output.read
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
