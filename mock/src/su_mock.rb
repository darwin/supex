#!/usr/bin/env ruby
# frozen_string_literal: true

# su-mock: Standalone headless SketchUp API mock server.
# Loads comprehensive SketchUp API mocks, then loads the real supex runtime
# (bridge_server.rb, tools.rb, vcad_tools.rb) and runs the TCP bridge server.
# Python integration tests connect over TCP exactly like they connect to real SketchUp.
#
# Usage:
#   ruby mock/src/su_mock.rb [--port PORT]

# Parse command line arguments
port = 9876
ARGV.each_with_index do |arg, i|
  port = ARGV[i + 1].to_i if arg == '--port' && ARGV[i + 1]
end

# Environment setup for headless operation
ENV['SUPEX_NO_AUTOSTART'] = '1'
ENV['SUPEX_SILENT'] = '1'
ENV['SUPEX_ALLOWED_ROOTS'] = '*'
ENV['SUPEX_CHECK_INTERVAL'] ||= '0.05'

# Load mock SketchUp API (must be loaded before any runtime code)
require_relative 'sketchup_api/core'

# Switch to blocking mode before loading runtime (so UI.start_timer captures correctly)
UI.enable_blocking_mode!

# Load the real supex runtime code
runtime_src = File.expand_path('../../runtime/src/supex_runtime', __dir__)
require File.join(runtime_src, 'bridge_server')

# Load test control and patch into BridgeServer
require_relative 'test_control'
SupexRuntime::BridgeServer.prepend(SketchupMock::TestControl)

# Start the server
warn "su-mock: Starting on port #{port}..."
server = SupexRuntime::BridgeServer.new(port: port)
server.start

# Signal handling for clean shutdown
trap('INT') do
  warn "\nsu-mock: Shutting down..."
  server.stop
  UI.stop_blocking_loop!
end

trap('TERM') do
  server.stop
  UI.stop_blocking_loop!
end

warn "su-mock: Ready on port #{port}"
$stdout.flush
$stderr.flush

# Run the blocking event loop (replaces SketchUp's UI thread)
UI.run_blocking_loop!
