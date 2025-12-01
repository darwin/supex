# frozen_string_literal: true

require 'minitest/autorun'
require 'socket'
require 'stringio'

# Mock UI module (SketchUp API) - must be defined before requiring runtime files
module UI
  @timers = {}
  @timer_id = 0

  class << self
    def start_timer(interval, repeat, &block)
      @timer_id += 1
      @timers[@timer_id] = { interval: interval, repeat: repeat, block: block }
      @timer_id
    end

    def stop_timer(id)
      @timers.delete(id)
    end

    def clear_timers
      @timers.clear
      @timer_id = 0
    end

    def timers
      @timers
    end
  end
end

# Require the files under test
require_relative '../src/supex_runtime/version'
require_relative '../src/supex_runtime/utils'
require_relative '../src/supex_runtime/repl_server'

# Override Utils.console_write for testing (after loading the real module)
module SupexRuntime
  module Utils
    class << self
      # Remove original method to avoid redefinition warning
      remove_method :console_write if method_defined?(:console_write)

      attr_accessor :console_output

      def console_write(message)
        @console_output ||= []
        @console_output << message
      end

      def clear_console_output
        @console_output = []
      end
    end
  end
end

# Helper to create a mock TCP server for client tests
class MockReplServer
  attr_reader :port, :received_messages

  def initialize(port: 0) # port 0 = auto-assign
    @server = TCPServer.new('127.0.0.1', port)
    @port = @server.addr[1]
    @received_messages = []
    @responses = {}
    @running = false
  end

  def set_response(code, response)
    @responses[code] = response
  end

  def start
    @running = true
    @thread = Thread.new do
      while @running
        begin
          client = @server.accept_nonblock
          message = client.read
          @received_messages << message
          response = @responses[message] || "=> #{eval(message).inspect}\n"
          client.write(response)
          client.close
        rescue Errno::EWOULDBLOCK, Errno::EAGAIN
          sleep 0.01
        rescue StandardError
          break unless @running
        end
      end
    end
  end

  def stop
    @running = false
    @thread&.join(1)
    @server&.close
  end
end

# Helper to extract eval_code for isolated testing
class EvalCodeTester
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
end
