#!/usr/bin/env ruby
# frozen_string_literal: true

# Supex REPL Client
# Connects to the Supex REPL server running inside SketchUp via JSON-RPC
#
# Usage:
#   ./repl              # Connect with default settings
#   ./repl -p 4433      # Connect to specific port
#   ./repl -h host      # Connect to specific host
#   ./repl --pry        # Use Pry with monkey-patched eval (RubyMine compatible)
#   ./repl --simple     # Simple line-by-line mode (default)
#
# RubyMine Integration:
#   When loaded via `pry -r repl.rb`, automatically patches Pry to send
#   code to the Supex REPL server without starting a new REPL loop.

require 'socket'
require 'json'

DEFAULT_PORT = 4433
DEFAULT_HOST = '127.0.0.1'
TIMEOUT = 5
CLIENT_NAME = 'repl-client'
CLIENT_VERSION = '2.0'
DEFAULT_RETRIES = 10
INITIAL_DELAY = 1.0
BACKOFF_MULTIPLIER = 2
AUTH_TOKEN = ENV.fetch('SUPEX_AUTH_TOKEN', nil)

# JSON-RPC REPL Client with persistent connection
class REPLClient
  attr_reader :host, :port, :session

  def initialize(host, port)
    @host = host
    @port = port
    @socket = nil
    @request_id = 0
    @session = nil
  end

  # Connect to server and perform hello handshake
  # @return [Hash] hello response
  def connect
    @socket = TCPSocket.new(@host, @port)
    response = send_hello
    @session = response.dig('result', 'session')
    response
  end

  # Check if connected
  def connected?
    !@socket.nil? && !@socket.closed?
  end

  # Send hello handshake
  # @return [Hash] response
  def send_hello
    params = {
      pid: Process.pid,
      name: CLIENT_NAME,
      version: CLIENT_VERSION
    }
    params[:token] = AUTH_TOKEN if AUTH_TOKEN && !AUTH_TOKEN.empty?
    send_request('hello', params)
  end

  # Evaluate code on server
  # @param code [String] Ruby code to evaluate
  # @return [Hash] response
  def eval(code)
    send_request('eval', { code: code })
  end

  # Send JSON-RPC request
  # @param method [String] method name
  # @param params [Hash] parameters
  # @return [Hash] response
  def send_request(method, params)
    raise 'Not connected' unless connected?

    @request_id += 1
    request = { jsonrpc: '2.0', method: method, id: @request_id, params: params }
    @socket.write("#{request.to_json}\n")
    @socket.flush
    read_response
  end

  # Read JSON-RPC response
  # @return [Hash] parsed response
  # @raise [IOError] when connection is closed
  def read_response
    line = @socket.gets
    raise IOError, 'Connection closed' unless line

    JSON.parse(line)
  rescue JSON::ParserError => e
    { 'error' => { 'message' => "Parse error: #{e.message}" } }
  end

  # Close connection
  def close
    @socket&.close
    @socket = nil
  end

  # Connect with retry and exponential backoff
  # @param max_retries [Integer, nil] max retry attempts (default: DEFAULT_RETRIES)
  # @return [Hash] hello response
  def connect_with_retry(max_retries: nil)
    retries = max_retries || Integer(ENV.fetch('SUPEX_REPL_RETRIES', DEFAULT_RETRIES))
    delay = INITIAL_DELAY

    (retries + 1).times do |attempt|
      return connect
    rescue Errno::ECONNREFUSED
      raise if attempt >= retries

      puts "Connection failed, retrying in #{delay.to_i}s... (#{attempt + 1}/#{retries})"
      sleep(delay)
      delay *= BACKOFF_MULTIPLIER
    end
  end

  # Reconnect after connection lost
  # @return [Boolean] true if reconnected
  def reconnect
    close
    puts 'Connection lost. Reconnecting...'
    connect_with_retry
    puts "Reconnected! Session: #{@session}"
    true
  rescue Errno::ECONNREFUSED
    false
  end

  # Evaluate code with automatic reconnection on connection errors
  # @param code [String] Ruby code to evaluate
  # @return [Hash] response
  def eval_with_reconnect(code)
    self.eval(code)
  rescue IOError, Errno::ECONNRESET, Errno::EPIPE
    return { 'error' => { 'message' => 'Reconnection failed' } } unless reconnect

    self.eval(code)
  end
end

# Check if server is available by attempting connection
def server_available?(host, port)
  client = REPLClient.new(host, port)
  response = client.connect
  client.close
  !response['error']
rescue StandardError
  false
end

# Simple REPL mode - line by line
def run_simple_repl(host, port)
  puts 'Supex REPL Client - Simple Mode (JSON-RPC)'
  puts "Connecting to #{host}:#{port}..."

  client = REPLClient.new(host, port)
  begin
    response = client.connect_with_retry
    if response['error']
      puts "Error: #{response['error']['message']}"
      exit 1
    end
  rescue Errno::ECONNREFUSED
    puts "Error: Cannot connect to REPL server at #{host}:#{port}"
    puts 'Make sure SketchUp is running with Supex extension loaded.'
    exit 1
  end

  puts "Connected! Session: #{client.session}"
  puts "Type 'exit' or Ctrl+D to quit."
  puts

  loop do
    line = Readline.readline('supex>> ', true)
    break if line.nil? || line.strip == 'exit'
    next if line.strip.empty?

    # Remove duplicate entries from history
    Readline::HISTORY.pop if Readline::HISTORY.length > 1 && Readline::HISTORY[-2] == line

    response = client.eval_with_reconnect(line)
    if response['error']
      puts "Error: #{response['error']['message']}"
    else
      output = response.dig('result', 'output')
      print output if output && !output.empty?
    end
  rescue Interrupt
    puts "\nUse 'exit' or Ctrl+D to quit."
  end

  client.close
  puts 'Goodbye!'
end

# Buffer for detecting rapid input (paste/send from IDE)
# Accumulates lines arriving within BUFFER_TIMEOUT_MS and sends as single block
class PryInputBuffer
  BUFFER_TIMEOUT_MS = Integer(ENV.fetch('SUPEX_REPL_BUFFER_MS', 50))
  PRY_COMMAND_PREFIXES = %w[ls cd help show show-source show-doc edit whereami ? ! . hist exit exit-all quit].freeze

  def initialize(pry_instance)
    @pry = pry_instance
    @buffer = []
    @mutex = Mutex.new
    @timer_thread = nil
  end

  # Add a line to buffer.
  # Returns :buffered if added to buffer, :bypass if should use original eval, :ignore if empty
  def add(line, options = {})
    result = classify_line(line)
    return result unless result == :buffered

    @mutex.synchronize do
      # Strip trailing newline but preserve the content
      @buffer << { line: line.to_s.chomp, options: options }
      start_flush_timer
    end
    :buffered
  end

  private

  # Classify line: :ignore (empty), :bypass (pry command), :buffered (normal code)
  def classify_line(line)
    return :ignore if line.nil?

    stripped = line.to_s.strip
    return :ignore if stripped.empty?

    return :bypass if PRY_COMMAND_PREFIXES.any? { |cmd| stripped.start_with?(cmd) }

    :buffered
  end

  def start_flush_timer
    @timer_thread&.kill
    @timer_thread = Thread.new do
      sleep(BUFFER_TIMEOUT_MS / 1000.0)
      @mutex.synchronize { do_flush }
    end
  end

  def do_flush
    return if @buffer.empty?

    combined = @buffer.map { |item| item[:line] }.join("\n")
    options = @buffer.first[:options]
    @buffer.clear

    # Execute in separate thread to avoid deadlock with mutex
    Thread.new { @pry.supex_original_eval(combined, options) }.join
  end
end

# Apply Pry monkey-patch to send code to Supex REPL server via JSON-RPC
# Uses persistent connection for the entire Pry session
def apply_pry_patch(host, port)
  $supex_client = REPLClient.new(host, port)

  begin
    response = $supex_client.connect_with_retry
    if response['error']
      puts "Supex REPL: Connection error: #{response['error']['message']}"
      return false
    end
  rescue Errno::ECONNREFUSED
    puts "Supex REPL: Cannot connect to #{host}:#{port}"
    return false
  end

  Pry.class_eval do
    # Store original eval for use by buffer flush
    alias_method :supex_original_eval, :eval

    # Lazy-initialize input buffer for this Pry instance
    def supex_input_buffer
      @supex_input_buffer ||= PryInputBuffer.new(self)
    end

    # Override eval to buffer rapid input (IDE paste detection)
    def eval(line, options = {})
      case supex_input_buffer.add(line, options)
      when :buffered
        true # Buffered - tell Pry to continue REPL loop
      when :ignore
        true # Empty line - ignore but continue REPL loop
      else # :bypass
        supex_original_eval(line, options) # Pry command - bypass buffering
      end
    end

    def evaluate_ruby(code)
      response = $supex_client.eval_with_reconnect(code)
      if response['error']
        output.puts "Error: #{response['error']['message']}"
      else
        out = response.dig('result', 'output')
        output.print(out) if out
      end
      nil
    end

    def show_result(_result)
      # no-op, result is printed by evaluate_ruby from server response
    end
  end

  at_exit { $supex_client&.close }
  true
end

# Pry mode - monkey-patch Pry's evaluate_ruby for RubyMine compatibility
def run_pry_repl(host, port)
  begin
    require 'pry'
  rescue LoadError
    puts 'Error: Pry gem not found. Install it with: gem install pry'
    exit 1
  end

  puts 'Supex REPL Client - Pry Mode (JSON-RPC)'
  puts "Connecting to #{host}:#{port}..."

  unless apply_pry_patch(host, port)
    puts 'Make sure SketchUp is running with Supex extension loaded.'
    exit 1
  end

  puts "Connected! Session: #{$supex_client.session}"
  puts "Type 'exit' or Ctrl+D to quit."
  puts

  # Start Pry
  Pry.start
end

# Detect if we're being loaded into an existing Pry session (e.g., via `pry -r repl.rb`)
# In this case, just apply the monkey-patch without starting a new REPL loop
if defined?(Pry) && !$supex_repl_standalone
  host = ENV.fetch('SUPEX_REPL_HOST', DEFAULT_HOST)
  port = Integer(ENV.fetch('SUPEX_REPL_PORT', DEFAULT_PORT))
  puts "Supex REPL: Connected to #{host}:#{port} (session: #{$supex_client.session})" if apply_pry_patch(host, port)
elsif __FILE__ == $PROGRAM_NAME
  # Running as standalone script - parse options and start REPL
  require 'optparse'
  require 'readline'

  $supex_repl_standalone = true

  options = {
    port: Integer(ENV.fetch('SUPEX_REPL_PORT', DEFAULT_PORT)),
    host: ENV.fetch('SUPEX_REPL_HOST', DEFAULT_HOST),
    mode: :simple
  }

  OptionParser.new do |opts|
    opts.banner = "Usage: #{$PROGRAM_NAME} [options]"

    opts.on('-p', '--port PORT', Integer, "REPL server port (default: #{DEFAULT_PORT})") do |p|
      options[:port] = p
    end

    opts.on('-h', '--host HOST', "REPL server host (default: #{DEFAULT_HOST})") do |h|
      options[:host] = h
    end

    opts.on('--pry', 'Use Pry with monkey-patched eval (for RubyMine)') do
      options[:mode] = :pry
    end

    opts.on('--simple', 'Simple line-by-line mode (default)') do
      options[:mode] = :simple
    end

    opts.on('--help', 'Show this help') do
      puts opts
      exit
    end
  end.parse!

  case options[:mode]
  when :pry
    run_pry_repl(options[:host], options[:port])
  else
    run_simple_repl(options[:host], options[:port])
  end
end
