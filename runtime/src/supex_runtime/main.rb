# frozen_string_literal: true

require 'sketchup'

require_relative 'version'
require_relative 'server'
require_relative 'utils'

module SupexRuntime
  # Main entry point for the Supex SketchUp extension
  # Provides a clean interface to start/stop the MCP server
  class Main
    class << self
      attr_accessor :server
    end
    @server = nil

    # Initialize and start the Supex server
    # @param port [Integer] server port (default: 9876)
    # @param host [String] server host (default: 127.0.0.1)
    def self.start_server(port: Server::DEFAULT_PORT, host: Server::DEFAULT_HOST)
      if @server&.running?
        Utils.console_write("Supex: Server is already running on #{host}:#{port}")
        return
      end

      begin
        @server = Server.new(port: port, host: host)
        @server.start

        Utils.console_write("Supex: Server started on #{host}:#{port}")
        Utils.console_write("Supex: Version #{VERSION}")
        Utils.console_write("Supex: SketchUp #{Sketchup.version} compatibility")

        add_menu_items
        true
      rescue StandardError => e
        Utils.console_write("Supex: Failed to start server: #{e.message}")
        Utils.console_write("Supex: #{e.backtrace.join("\n")}")
        false
      end
    end

    # Stop the Supex server
    def self.shutdown_server
      if @server&.running?
        @server.stop
        @server = nil
        Utils.console_write('Supex: Server stopped')
        remove_menu_items
        true
      else
        Utils.console_write('Supex: Server is not running')
        false
      end
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
      if @server&.running?
        {
          running: true,
          version: VERSION,
          sketchup_version: Sketchup.version,
          mcp_version: MCP_VERSION,
          required_sketchup: REQUIRED_SKETCHUP_VERSION
        }
      else
        {
          running: false,
          version: VERSION
        }
      end
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
        export.rb joinery.rb server.rb main.rb
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
      supex_runtime_menu.add_item('Stop Server') { stop_server }
      supex_runtime_menu.add_item('Restart Server') { restart_server }
      supex_runtime_menu.add_item('Reload Extension') { reload_extension }
      supex_runtime_menu.add_separator
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
      message = if status[:running]
                  "Supex Server Status: RUNNING\n\n" \
                    "Version: #{status[:version]}\n" \
                    "SketchUp: #{status[:sketchup_version]}\n" \
                    "MCP Version: #{status[:mcp_version]}"
                else
                  "Supex Server Status: STOPPED\n\n" \
                    "Version: #{status[:version]}"
                end

      UI.messagebox(message, MB_OK)
    end

    # Show about dialog
    def self.show_about_dialog
      message = "Supex v#{VERSION}\n\n" \
                "A modern SketchUp Model Context Protocol server.\n" \
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
