# frozen_string_literal: true

require 'sketchup'

require_relative 'version'
require_relative 'server'
require_relative 'repl_server'
require_relative 'utils'

module SupexRuntime
  # Main entry point for the Supex SketchUp extension
  # Provides a clean interface to start/stop the MCP and REPL servers
  class Main
    class << self
      attr_accessor :server, :repl_server
    end
    @server = nil
    @repl_server = nil

    # Initialize and start the Supex server (MCP and optionally REPL)
    # @param port [Integer] MCP server port (default: 9876)
    # @param host [String] server host (default: 127.0.0.1)
    # @param repl [Boolean] start REPL server (default: true unless SUPEX_REPL_DISABLED)
    def self.start_server(port: Server::DEFAULT_PORT, host: Server::DEFAULT_HOST, repl: nil)
      if @server&.running?
        Utils.console_write("Supex: Server is already running on #{host}:#{port}")
        return
      end

      begin
        @server = Server.new(port: port, host: host)
        @server.start

        Utils.console_write("Supex: MCP server started on #{host}:#{port}")
        Utils.console_write("Supex: Version #{VERSION}")
        Utils.console_write("Supex: SketchUp #{Sketchup.version} compatibility")

        # Start REPL server unless explicitly disabled
        repl_enabled = repl.nil? ? ENV['SUPEX_REPL_DISABLED'] != '1' : repl
        start_repl_server if repl_enabled

        add_menu_items
        true
      rescue StandardError => e
        Utils.console_write("Supex: Failed to start server: #{e.message}")
        Utils.console_write("Supex: #{e.backtrace.join("\n")}")
        false
      end
    end

    # Start the REPL server separately
    # @param port [Integer] REPL server port (default: 4433)
    # @param host [String] server host (default: 127.0.0.1)
    def self.start_repl_server(port: ReplServer::DEFAULT_REPL_PORT, host: ReplServer::DEFAULT_REPL_HOST)
      if @repl_server&.running?
        Utils.console_write("Supex: REPL server is already running")
        return false
      end

      begin
        @repl_server = ReplServer.new(port: port, host: host)
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

    # Stop all Supex servers (MCP and REPL)
    def self.shutdown_server
      stopped = false

      # Stop REPL server first
      if @repl_server&.running?
        @repl_server.stop
        @repl_server = nil
        Utils.console_write('Supex: REPL server stopped')
        stopped = true
      end

      # Stop MCP server
      if @server&.running?
        @server.stop
        @server = nil
        Utils.console_write('Supex: MCP server stopped')
        remove_menu_items
        stopped = true
      end

      Utils.console_write('Supex: No servers were running') unless stopped
      stopped
    end

    class << self
      alias stop_server shutdown_server
    end

    # Check if server is running
    # @return [Boolean] true if server is running
    def self.server_running?
      @server&.running? || false
    end

    # Get server status information
    # @return [Hash] server status details
    def self.server_status
      status = {
        version: VERSION,
        mcp: {
          running: @server&.running? || false,
          port: @server&.running? ? Server::DEFAULT_PORT : nil
        },
        repl: {
          running: @repl_server&.running? || false,
          port: @repl_server&.running? ? @repl_server.port : nil
        }
      }

      if @server&.running?
        status[:sketchup_version] = Sketchup.version
        status[:mcp_version] = MCP_VERSION
        status[:required_sketchup] = REQUIRED_SKETCHUP_VERSION
      end

      status
    end

    # Check if any server is running
    def self.any_server_running?
      server_running? || repl_server_running?
    end

    # Check if REPL server is running
    def self.repl_server_running?
      @repl_server&.running? || false
    end

    # Restart the server (stop then start)
    # @param port [Integer] server port
    # @param host [String] server host
    def self.restart_server(port: Server::DEFAULT_PORT, host: Server::DEFAULT_HOST)
      stop_server
      sleep(0.5) # Brief pause to ensure clean shutdown
      start_server(port: port, host: host)
    end

    # Reload the extension by unloading and reloading all source files
    # This is useful during development to pick up code changes
    def self.reload_extension
      Utils.console_write('Supex: Reloading extension...')

      begin
        was_running = @server&.running?
        stop_server if was_running

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
        export.rb joinery.rb server.rb repl_server.rb main.rb
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
    def self.reload_main_extension_file
      extension_dir = __dir__
      main_extension_dir = File.expand_path(File.join(extension_dir, '..'))
      main_file = File.join(main_extension_dir, 'supex_runtime.rb')
      load(main_file) if File.exist?(main_file)
    end

    # Restart server if it was running before reload
    def self.restart_if_was_running(was_running)
      return unless was_running

      sleep(1)
      start_server
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
      supex_runtime_menu.add_item('Stop All Servers') { stop_server }
      supex_runtime_menu.add_item('Restart All Servers') { restart_server }
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

      mcp_status = status[:mcp][:running] ? "RUNNING (port #{status[:mcp][:port]})" : 'STOPPED'
      repl_status = status[:repl][:running] ? "RUNNING (port #{status[:repl][:port]})" : 'STOPPED'

      message = "Supex Server Status\n\n" \
                "Version: #{status[:version]}\n\n" \
                "MCP Server: #{mcp_status}\n" \
                "REPL Server: #{repl_status}"

      if status[:mcp][:running]
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

# Auto-start server when extension loads (unless disabled)
unless defined?(SUPEX_NO_AUTOSTART) && SUPEX_NO_AUTOSTART
  # Use a timer to start after SketchUp finishes loading
  UI.start_timer(1.0, false) do
    SupexRuntime::Main.start_server
  end
end
