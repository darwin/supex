# frozen_string_literal: true

require 'sketchup'

require_relative 'version'
require_relative 'bridge_server'
require_relative 'repl_server'
require_relative 'utils'

module SupexRuntime
  # Main entry point for the Supex SketchUp extension
  # Provides a clean interface to start/stop the MCP and REPL servers
  class Main
    class << self
      attr_accessor :bridge_server, :repl_server
    end
    @bridge_server = nil
    @repl_server = nil

    # Initialize and start all Supex servers (bridge and optionally REPL)
    # @param repl [Boolean] start REPL server (default: true unless SUPEX_REPL_DISABLED)
    def self.start(repl: nil)
      load_stdlib
      Utils.console_write("Supex: Version #{VERSION}")
      Utils.console_write("Supex: SketchUp #{Sketchup.version} compatibility")

      start_bridge_server

      # Start REPL server unless explicitly disabled
      repl_enabled = repl.nil? ? ENV['SUPEX_REPL_DISABLED'] != '1' : repl
      start_repl_server if repl_enabled

      add_menu_items
      true
    end

    # Start the bridge server
    # @param port [Integer] bridge server port (default: 9876)
    # @param host [String] server host (default: 127.0.0.1)
    def self.start_bridge_server(port: BridgeServer::DEFAULT_PORT, host: BridgeServer::DEFAULT_HOST)
      if @bridge_server&.running?
        Utils.console_write("Supex: Bridge server is already running on #{host}:#{port}")
        return false
      end

      begin
        @bridge_server = BridgeServer.new(port: port, host: host)
        @bridge_server.start
        Utils.console_write("Supex: Bridge server started on #{host}:#{port}")
        true
      rescue StandardError => e
        Utils.console_write("Supex: Failed to start bridge server: #{e.message}")
        Utils.console_write("Supex: #{e.backtrace.join("\n")}")
        false
      end
    end

    # Start the REPL server separately
    # @param port [Integer] REPL server port (default: 4433)
    # @param host [String] server host (default: 127.0.0.1)
    def self.start_repl_server(port: REPLServer::DEFAULT_REPL_PORT, host: REPLServer::DEFAULT_REPL_HOST)
      if @repl_server&.running?
        Utils.console_write('Supex: REPL server is already running')
        return false
      end

      begin
        @repl_server = REPLServer.new(port: port, host: host)
        if @repl_server.start
          Utils.console_write("Supex: REPL server started on #{host}:#{port}")
          true
        else
          Utils.console_write('Supex: REPL server failed to start (Pry not available)')
          @repl_server = nil
          false
        end
      rescue StandardError => e
        Utils.console_write("Supex: Failed to start REPL server: #{e.message}")
        @repl_server = nil
        false
      end
    end

    # Stop the REPL server
    def self.stop_repl_server
      if @repl_server&.running?
        @repl_server.stop
        @repl_server = nil
        Utils.console_write('Supex: REPL server stopped')
        true
      else
        Utils.console_write('Supex: REPL server is not running')
        false
      end
    end

    # Stop all Supex servers (bridge and REPL)
    def self.stop
      stopped = false

      # Stop REPL server first
      if @repl_server&.running?
        @repl_server.stop
        @repl_server = nil
        Utils.console_write('Supex: REPL server stopped')
        stopped = true
      end

      # Stop bridge server
      if @bridge_server&.running?
        @bridge_server.stop
        @bridge_server = nil
        Utils.console_write('Supex: Bridge server stopped')
        remove_menu_items
        stopped = true
      end

      Utils.console_write('Supex: No servers were running') unless stopped
      stopped
    end

    # Check if bridge server is running
    # @return [Boolean] true if bridge server is running
    def self.bridge_server_running?
      @bridge_server&.running? || false
    end

    # Get server status information
    # @return [Hash] server status details
    def self.server_status
      status = {
        version: VERSION,
        bridge: {
          running: @bridge_server&.running? || false,
          port: @bridge_server&.running? ? BridgeServer::DEFAULT_PORT : nil
        },
        repl: {
          running: @repl_server&.running? || false,
          port: @repl_server&.running? ? @repl_server.port : nil
        }
      }

      if @bridge_server&.running?
        status[:sketchup_version] = Sketchup.version
        status[:mcp_version] = MCP_VERSION
        status[:required_sketchup] = REQUIRED_SKETCHUP_VERSION
      end

      status
    end

    # Check if any server is running
    def self.any_server_running?
      bridge_server_running? || repl_server_running?
    end

    # Check if REPL server is running
    def self.repl_server_running?
      @repl_server&.running? || false
    end

    # Restart all servers (stop then start)
    def self.restart
      stop
      sleep(0.5) # Brief pause to ensure clean shutdown
      start
    end

    # Reload the extension by unloading and reloading all source files
    # This is useful during development to pick up code changes
    def self.reload_extension
      Utils.console_write('Supex: Reloading extension...')

      begin
        was_running = @bridge_server&.running?
        stop if was_running

        remove_extension_constants
        unload_extension_files

        GC.start
        reload_main_extension_file

        Utils.console_write('Supex: Extension reloaded successfully')
        restart_if_was_running(was_running)
        true
      rescue StandardError => e
        Utils.console_write("Supex: Failed to reload extension: #{e.message}")
        Utils.console_write("Supex: #{e.backtrace.join("\n")}")
        false
      end
    end

    # Remove SupexRuntime constants to avoid redefinition warnings
    def self.remove_extension_constants
      return unless defined?(SupexRuntime::VERSION)

      constants_to_remove = %i[
        VERSION REQUIRED_SKETCHUP_VERSION MCP_VERSION
        EXTENSION_NAME EXTENSION_DESCRIPTION EXTENSION_CREATOR EXTENSION_COPYRIGHT
      ]
      constants_to_remove.each do |const|
        SupexRuntime.send(:remove_const, const)
      rescue StandardError
        nil
      end
    end

    # Unload extension files from $LOADED_FEATURES
    def self.unload_extension_files
      files_to_reload = %w[
        version.rb utils.rb geometry.rb materials.rb
        export.rb joinery.rb batch_screenshot.rb tools.rb
        bridge_server.rb repl_server.rb main.rb
      ]
      extension_dir = __dir__

      files_to_reload.each do |file|
        full_path = File.join(extension_dir, file)
        loaded_files = $LOADED_FEATURES.select do |f|
          f == full_path || f.end_with?("/supex_runtime/#{file}")
        end
        loaded_files.each do |loaded_file|
          $LOADED_FEATURES.delete(loaded_file)
          Utils.console_write("Supex: Unloaded #{loaded_file}")
        end
      end
    end

    # Reload the main extension file
    # Note: We load main.rb directly, not supex_runtime.rb, because supex_runtime.rb
    # has a file_loaded? guard that prevents re-execution after initial load
    def self.reload_main_extension_file
      extension_dir = __dir__
      main_file = File.join(extension_dir, 'main.rb')
      load(main_file) if File.exist?(main_file)
    end

    # Restart server if it was running before reload
    def self.restart_if_was_running(was_running)
      return unless was_running

      sleep(1)
      start
    end

    # Load the Supex Standard Library
    # @return [Boolean] true if stdlib was loaded successfully
    def self.load_stdlib
      stdlib_path = ENV['SUPEX_STDLIB_PATH'] ||
                    File.expand_path('../../../stdlib/src/supex_stdlib.rb', __dir__)

      if File.exist?(stdlib_path)
        require stdlib_path
        Utils.console_write("Supex: Stdlib v#{SupexStdlib::VERSION} loaded")
        true
      else
        Utils.console_write('Supex: Stdlib not found (optional)')
        false
      end
    rescue StandardError => e
      Utils.console_write("Supex: Failed to load stdlib: #{e.message}")
      false
    end

    # Add menu items to SketchUp's Extensions menu
    def self.add_menu_items
      # Skip if menu already exists (simple check - menu creation will fail if exists)
      begin
        extensions_menu = UI.menu('Extensions')
        supex_runtime_menu = extensions_menu.add_submenu('Supex')
      rescue ArgumentError
        # Menu already exists, skip creation
        return
      end

      supex_runtime_menu.add_item('Server Status') { show_server_status }
      supex_runtime_menu.add_separator
      supex_runtime_menu.add_item('Stop All Servers') { stop }
      supex_runtime_menu.add_item('Restart All Servers') { restart }
      supex_runtime_menu.add_separator
      supex_runtime_menu.add_item('Start REPL') { start_repl_server }
      supex_runtime_menu.add_item('Stop REPL') { stop_repl_server }
      supex_runtime_menu.add_separator
      supex_runtime_menu.add_item('Reload Extension') { reload_extension }
      supex_runtime_menu.add_item('Show Console') { Utils.show_console }
      supex_runtime_menu.add_item('About') { show_about_dialog }
    end

    # Remove menu items from SketchUp's Extensions menu
    def self.remove_menu_items
      # SketchUp doesn't provide a direct way to remove menu items
      # They will be removed when SketchUp restarts
    end

    # Show server status dialog
    def self.show_server_status
      status = server_status

      bridge_status = status[:bridge][:running] ? "RUNNING (port #{status[:bridge][:port]})" : 'STOPPED'
      repl_status = status[:repl][:running] ? "RUNNING (port #{status[:repl][:port]})" : 'STOPPED'

      message = "Supex Server Status\n\n" \
                "Version: #{status[:version]}\n\n" \
                "Bridge Server: #{bridge_status}\n" \
                "REPL Server: #{repl_status}"

      if status[:bridge][:running]
        message += "\n\nSketchUp: #{status[:sketchup_version]}\n" \
                   "MCP Version: #{status[:mcp_version]}"
      end

      UI.messagebox(message, MB_OK)
    end

    # Show about dialog
    def self.show_about_dialog
      message = "Supex v#{VERSION}\n\n" \
                "A SketchUp Model Context Protocol server.\n" \
                "Provides AI-accessible tools for SketchUp automation.\n\n" \
                "Supported SketchUp: #{REQUIRED_SKETCHUP_VERSION}+\n" \
                "Current SketchUp: #{Sketchup.version}\n" \
                "MCP Version: #{MCP_VERSION}"

      UI.messagebox(message, MB_OK)
    end
  end
end

# Auto-start server when extension loads (unless disabled via SUPEX_NO_AUTOSTART=1)
unless ENV['SUPEX_NO_AUTOSTART'] == '1'
  # Use a timer to start after SketchUp finishes loading
  UI.start_timer(1.0, false) do
    SupexRuntime::Main.start
  end
end
