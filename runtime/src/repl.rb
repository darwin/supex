#!/usr/bin/env ruby
# frozen_string_literal: true

# Supex REPL Client
# Connects to the Supex REPL server running inside SketchUp
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

DEFAULT_PORT = 4433
DEFAULT_HOST = '127.0.0.1'
TIMEOUT = 5

# Send code to REPL server and get response
def send_to_repl(code, host, port, timeout = TIMEOUT)
  socket = Socket.new(Socket::AF_INET, Socket::SOCK_STREAM, 0)
  sockaddr = Socket.pack_sockaddr_in(port, host)

  begin
    socket.connect_nonblock(sockaddr)
  rescue Errno::EINPROGRESS
    raise Timeout::Error, 'Connection timeout' unless IO.select(nil, [socket], nil, timeout)

    begin
      socket.connect_nonblock(sockaddr)
    rescue Errno::EISCONN
      # Connected
    end
  end

  socket.write(code)
  socket.close_write
  socket.read
rescue Errno::ECONNREFUSED
  nil
ensure
  socket&.close
end

# Check if server is available
def server_available?(host, port)
  result = send_to_repl('1 + 1', host, port, 2)
  !result.nil?
rescue StandardError
  false
end

# Simple REPL mode - line by line
def run_simple_repl(host, port)
  puts "Supex REPL Client - Simple Mode"
  puts "Connecting to #{host}:#{port}..."

  unless server_available?(host, port)
    puts "Error: Cannot connect to REPL server at #{host}:#{port}"
    puts 'Make sure SketchUp is running with Supex extension loaded.'
    exit 1
  end

  puts "Connected! Type 'exit' or Ctrl+D to quit."
  puts

  loop do
    begin
      line = Readline.readline('supex>> ', true)
      break if line.nil? || line.strip == 'exit'
      next if line.strip.empty?

      # Remove duplicate entries from history
      if Readline::HISTORY.length > 1 && Readline::HISTORY[-2] == line
        Readline::HISTORY.pop
      end

      result = send_to_repl(line, host, port)
      if result.nil?
        puts 'Error: Connection lost. Server may have stopped.'
        break
      end
      puts result unless result.empty?
    rescue Interrupt
      puts "\nUse 'exit' or Ctrl+D to quit."
    end
  end

  puts 'Goodbye!'
end

# Apply Pry monkey-patch to send code to Supex REPL server
# This patches evaluate_ruby instead of eval because:
# - eval() receives input line by line
# - Pry accumulates lines until expression is complete
# - evaluate_ruby() receives the complete multiline expression
def apply_pry_patch(host, port)
  $supex_repl_host = host
  $supex_repl_port = port

  Pry.class_eval do
    def evaluate_ruby(code)
      timeout = 5
      socket = Socket.new(Socket::AF_INET, Socket::SOCK_STREAM, 0)
      sockaddr = Socket.pack_sockaddr_in($supex_repl_port, $supex_repl_host)

      begin
        socket.connect_nonblock(sockaddr)
      rescue Errno::EINPROGRESS
        raise Timeout::Error unless IO.select(nil, [socket], nil, timeout)
        retry
      rescue Errno::EISCONN
        socket.write(code)
        socket.close_write
        out = socket.read
        output.print(out)
      rescue Errno::ECONNREFUSED => e
        output.puts "Connection refused: #{e.message}"
      ensure
        socket&.close
      end
      nil
    end

    def show_result(_result)
      # no-op, result is printed by evaluate_ruby from server response
    end
  end
end

# Pry mode - monkey-patch Pry's evaluate_ruby for RubyMine compatibility
def run_pry_repl(host, port)
  begin
    require 'pry'
  rescue LoadError
    puts "Error: Pry gem not found. Install it with: gem install pry"
    exit 1
  end

  puts "Supex REPL Client - Pry Mode"
  puts "Connecting to #{host}:#{port}..."

  unless server_available?(host, port)
    puts "Error: Cannot connect to REPL server at #{host}:#{port}"
    puts 'Make sure SketchUp is running with Supex extension loaded.'
    exit 1
  end

  puts "Connected! Type 'exit' or Ctrl+D to quit."
  puts

  apply_pry_patch(host, port)

  # Start Pry
  Pry.start
end

# Detect if we're being loaded into an existing Pry session (e.g., via `pry -r repl.rb`)
# In this case, just apply the monkey-patch without starting a new REPL loop
if defined?(Pry) && !$supex_repl_standalone
  host = ENV.fetch('SUPEX_REPL_HOST', DEFAULT_HOST)
  port = Integer(ENV.fetch('SUPEX_REPL_PORT', DEFAULT_PORT))
  apply_pry_patch(host, port)
  puts "Supex REPL: Pry patched to send code to #{host}:#{port}"
else
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
