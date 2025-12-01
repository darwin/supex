# frozen_string_literal: true

require_relative 'test_helper'
require_relative '../src/supex_runtime/bridge_server'
require_relative '../src/supex_runtime/main'

class TestMain < Minitest::Test
  def setup
    UI.clear_timers
    UI.reset_ui_mocks
    SupexRuntime::Utils.clear_console_output
    Sketchup.reset_mocks

    # Ensure servers are stopped before each test
    SupexRuntime::Main.stop
    SupexRuntime::Main.instance_variable_set(:@bridge_server, nil)
    SupexRuntime::Main.instance_variable_set(:@repl_server, nil)
  end

  def teardown
    SupexRuntime::Main.stop
    UI.clear_timers
    SupexRuntime::Utils.clear_console_output
  end

  # ==========================================================================
  # Server status tests (before start)
  # ==========================================================================

  def test_bridge_running_initial
    refute SupexRuntime::Main.bridge_server_running?
  end

  def test_repl_running_initial
    refute SupexRuntime::Main.repl_server_running?
  end

  def test_any_server_running_initial
    refute SupexRuntime::Main.any_server_running?
  end

  # ==========================================================================
  # start_bridge_server tests
  # ==========================================================================

  def test_start_bridge_server
    result = SupexRuntime::Main.start_bridge_server(port: 0)

    assert result
    assert SupexRuntime::Main.bridge_server_running?
  end

  def test_start_bridge_server_idempotent
    SupexRuntime::Main.start_bridge_server(port: 0)

    result = SupexRuntime::Main.start_bridge_server(port: 0)

    refute result, 'Second start should return false'
    assert SupexRuntime::Main.bridge_server_running?
  end

  def test_start_bridge_server_custom_port
    result = SupexRuntime::Main.start_bridge_server(port: 0, host: '127.0.0.1')

    assert result
    assert SupexRuntime::Main.bridge_server_running?
  end

  # ==========================================================================
  # start_repl_server tests
  # ==========================================================================

  def test_start_repl_server
    # REPL server may fail if Pry is not available, which is OK
    result = SupexRuntime::Main.start_repl_server(port: 0)

    # Result depends on Pry availability
    if result
      assert SupexRuntime::Main.repl_server_running?
    else
      refute SupexRuntime::Main.repl_server_running?
    end
  end

  def test_start_repl_server_idempotent
    first_result = SupexRuntime::Main.start_repl_server(port: 0)

    # Only test idempotency if first start succeeded
    return unless first_result

    second_result = SupexRuntime::Main.start_repl_server(port: 0)

    refute second_result, 'Second start should return false'
  end

  # ==========================================================================
  # stop tests
  # ==========================================================================

  def test_stop_not_running
    result = SupexRuntime::Main.stop

    refute result
    assert_any_console_message_includes('No servers were running')
  end

  def test_stop_bridge_server
    SupexRuntime::Main.start_bridge_server(port: 0)
    assert SupexRuntime::Main.bridge_server_running?

    result = SupexRuntime::Main.stop

    assert result
    refute SupexRuntime::Main.bridge_server_running?
  end

  def test_stop_repl_server_only
    first_result = SupexRuntime::Main.start_repl_server(port: 0)
    return unless first_result # Skip if REPL not available

    result = SupexRuntime::Main.stop_repl_server

    assert result
    refute SupexRuntime::Main.repl_server_running?
  end

  def test_stop_repl_server_not_running
    result = SupexRuntime::Main.stop_repl_server

    refute result
  end

  # ==========================================================================
  # start (both servers) tests
  # Note: Main.start() uses default port 9876 which may conflict.
  # These tests verify the return value and REPL control logic, not actual running state.
  # ==========================================================================

  def test_start_returns_true
    # start() always returns true regardless of whether servers started successfully
    result = SupexRuntime::Main.start(repl: false)

    assert result
  end

  def test_start_repl_disabled_via_param
    # Verify REPL is not started when repl: false
    SupexRuntime::Main.start(repl: false)

    # REPL should definitely not be running
    refute SupexRuntime::Main.repl_server_running?
  end

  def test_start_repl_disabled_via_env
    original = ENV['SUPEX_REPL_DISABLED']
    ENV['SUPEX_REPL_DISABLED'] = '1'

    SupexRuntime::Main.start

    # REPL should definitely not be running
    refute SupexRuntime::Main.repl_server_running?
  ensure
    ENV['SUPEX_REPL_DISABLED'] = original
  end

  # ==========================================================================
  # restart tests
  # ==========================================================================

  def test_restart_with_manual_server
    # Start bridge server manually with port 0
    SupexRuntime::Main.start_bridge_server(port: 0)
    assert SupexRuntime::Main.bridge_server_running?

    # Stop manually (restart would use default port which may conflict)
    SupexRuntime::Main.stop

    refute SupexRuntime::Main.bridge_server_running?
  end

  # ==========================================================================
  # server_status tests
  # ==========================================================================

  def test_server_status_structure
    status = SupexRuntime::Main.server_status

    assert status.key?(:version)
    assert status.key?(:bridge)
    assert status.key?(:repl)
    assert status[:bridge].key?(:running)
    assert status[:repl].key?(:running)
  end

  def test_server_status_not_running
    status = SupexRuntime::Main.server_status

    refute status[:bridge][:running]
    refute status[:repl][:running]
    assert_nil status[:bridge][:port]
  end

  def test_server_status_running
    # Start with explicit port 0 to avoid conflicts
    SupexRuntime::Main.start_bridge_server(port: 0)

    status = SupexRuntime::Main.server_status

    assert status[:bridge][:running]
    assert status[:sketchup_version]
    assert status[:mcp_version]
  end

  # ==========================================================================
  # any_server_running tests
  # ==========================================================================

  def test_any_server_with_bridge_only
    SupexRuntime::Main.start_bridge_server(port: 0)

    assert SupexRuntime::Main.any_server_running?
  end

  def test_any_server_with_repl_only
    result = SupexRuntime::Main.start_repl_server(port: 0)
    return unless result # Skip if REPL not available

    assert SupexRuntime::Main.any_server_running?
  end

  # ==========================================================================
  # Menu management tests
  # ==========================================================================

  def test_add_menu_creates_submenu
    SupexRuntime::Main.add_menu_items

    extensions_menu = UI.menus['Extensions']
    assert extensions_menu
    assert extensions_menu.submenus['Supex']
  end

  def test_add_menu_items_populated
    SupexRuntime::Main.add_menu_items

    supex_menu = UI.menus['Extensions'].submenus['Supex']
    labels = supex_menu.items.map { |i| i[:label] }.compact

    assert_includes labels, 'Server Status'
    assert_includes labels, 'Stop All Servers'
    assert_includes labels, 'Reload Extension'
  end

  def test_show_server_status_dialog
    SupexRuntime::Main.show_server_status

    assert UI.messageboxes.any?, 'Messagebox should be shown'
    assert_includes UI.messageboxes.first[:message], 'Server Status'
  end

  def test_show_about_dialog
    SupexRuntime::Main.show_about_dialog

    assert UI.messageboxes.any?, 'Messagebox should be shown'
    assert_includes UI.messageboxes.first[:message], 'Supex'
  end

  private

  def assert_any_console_message_includes(substring)
    messages = SupexRuntime::Utils.console_output || []
    found = messages.any? { |m| m.include?(substring) }
    assert found, "Expected console output to include '#{substring}', got: #{messages.inspect}"
  end
end
