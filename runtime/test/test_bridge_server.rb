# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/bridge_server'

class TestBridgeServer < Minitest::Test
  def setup
    UI.clear_timers
    UI.reset_ui_mocks
    SupexRuntime::Utils.clear_console_output
    Sketchup.reset_mocks
  end

  def teardown
    @server&.stop
    UI.clear_timers
    SupexRuntime::Utils.clear_console_output
  end

  # ==========================================================================
  # Initialization tests
  # ==========================================================================

  def test_initialize_defaults
    server = SupexRuntime::BridgeServer.new

    assert_equal 9876, server.instance_variable_get(:@port)
    assert_equal '127.0.0.1', server.instance_variable_get(:@host)
  end

  def test_initialize_custom_port
    server = SupexRuntime::BridgeServer.new(port: 9999)

    assert_equal 9999, server.instance_variable_get(:@port)
  end

  def test_initialize_custom_host
    server = SupexRuntime::BridgeServer.new(host: '0.0.0.0')

    assert_equal '0.0.0.0', server.instance_variable_get(:@host)
  end

  def test_running_initially_false
    server = SupexRuntime::BridgeServer.new(port: 0)

    refute server.running?
  end

  # ==========================================================================
  # complete_json? tests
  # ==========================================================================

  def test_complete_json_with_newline
    server = SupexRuntime::BridgeServer.new(port: 0)

    assert server.send(:complete_json?, "{\"test\": true}\n")
  end

  def test_complete_json_without_newline
    server = SupexRuntime::BridgeServer.new(port: 0)

    # Without newline, message is not complete (regardless of balanced braces)
    refute server.send(:complete_json?, '{"test": true}')
  end

  def test_complete_json_incomplete
    server = SupexRuntime::BridgeServer.new(port: 0)

    refute server.send(:complete_json?, '{"test": ')
  end

  def test_complete_json_nested_without_newline
    server = SupexRuntime::BridgeServer.new(port: 0)

    # Without newline, message is not complete (regardless of nesting)
    refute server.send(:complete_json?, '{"outer": {"inner": true}}')
  end

  def test_complete_json_with_braces_in_string
    server = SupexRuntime::BridgeServer.new(port: 0)

    # JSON with braces in string values should work correctly with newline
    assert server.send(:complete_json?, "{\"msg\": \"{test}\"}\n")
  end

  # ==========================================================================
  # format_args tests
  # ==========================================================================

  def test_format_args_empty
    server = SupexRuntime::BridgeServer.new(port: 0)

    assert_equal '', server.send(:format_args, {})
    assert_equal '', server.send(:format_args, nil)
  end

  def test_format_args_simple
    server = SupexRuntime::BridgeServer.new(port: 0)

    result = server.send(:format_args, { name: 'test' })

    assert_includes result, 'name:'
  end

  def test_format_args_truncates_long_strings
    server = SupexRuntime::BridgeServer.new(port: 0)
    long_string = 'x' * 300

    result = server.send(:format_args, { code: long_string })

    assert_includes result, '...'
    assert result.length < 300
  end

  # ==========================================================================
  # ConnectionContext tests
  # ==========================================================================

  def test_connection_context_not_identified
    context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)

    refute context.identified?
  end

  def test_connection_context_identified
    context = SupexRuntime::BridgeServer::ConnectionContext.new(
      client_info: { name: 'test', version: '1.0', agent: 'test', pid: 123 }
    )

    assert context.identified?
  end

  # ==========================================================================
  # handle_hello tests (unit)
  # ==========================================================================

  def test_handle_hello_success
    server = SupexRuntime::BridgeServer.new(port: 0)
    context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
    request = {
      'jsonrpc' => '2.0',
      'method' => 'hello',
      'params' => { 'name' => 'test', 'version' => '1.0', 'agent' => 'cli', 'pid' => 123 },
      'id' => 1
    }

    response = server.send(:handle_hello, request, context)

    assert response[:result][:success]
    assert context.identified?
    assert_equal 'test', context.client_info[:name]
  end

  def test_handle_hello_missing_name
    server = SupexRuntime::BridgeServer.new(port: 0)
    context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
    request = {
      'jsonrpc' => '2.0',
      'method' => 'hello',
      'params' => { 'version' => '1.0', 'agent' => 'cli', 'pid' => 123 },
      'id' => 1
    }

    response = server.send(:handle_hello, request, context)

    assert response[:error]
    refute context.identified?
  end

  def test_handle_hello_missing_all_params
    server = SupexRuntime::BridgeServer.new(port: 0)
    context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
    request = {
      'jsonrpc' => '2.0',
      'method' => 'hello',
      'params' => {},
      'id' => 1
    }

    response = server.send(:handle_hello, request, context)

    assert response[:error]
    assert_equal(-32_600, response[:error][:code])
  end

  # ==========================================================================
  # Token authentication tests
  # ==========================================================================

  def test_handle_hello_with_valid_token
    # Temporarily set AUTH_TOKEN via constant redefinition
    original_token = SupexRuntime::BridgeServer::AUTH_TOKEN
    SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
    SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, 'test-secret-token')

    begin
      server = SupexRuntime::BridgeServer.new(port: 0)
      context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
      request = {
        'jsonrpc' => '2.0',
        'method' => 'hello',
        'params' => {
          'name' => 'test', 'version' => '1.0', 'agent' => 'cli', 'pid' => 123,
          'token' => 'test-secret-token'
        },
        'id' => 1
      }

      response = server.send(:handle_hello, request, context)

      assert response[:result][:success], "Hello should succeed with valid token: #{response.inspect}"
      assert context.identified?
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
      SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, original_token)
    end
  end

  def test_handle_hello_with_invalid_token
    original_token = SupexRuntime::BridgeServer::AUTH_TOKEN
    SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
    SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, 'test-secret-token')

    begin
      server = SupexRuntime::BridgeServer.new(port: 0)
      context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
      request = {
        'jsonrpc' => '2.0',
        'method' => 'hello',
        'params' => {
          'name' => 'test', 'version' => '1.0', 'agent' => 'cli', 'pid' => 123,
          'token' => 'wrong-token'
        },
        'id' => 1
      }

      response = server.send(:handle_hello, request, context)

      assert response[:error], "Hello should fail with invalid token: #{response.inspect}"
      assert_equal(-32_001, response[:error][:code])
      refute context.identified?
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
      SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, original_token)
    end
  end

  def test_handle_hello_with_missing_token_when_required
    original_token = SupexRuntime::BridgeServer::AUTH_TOKEN
    SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
    SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, 'test-secret-token')

    begin
      server = SupexRuntime::BridgeServer.new(port: 0)
      context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
      request = {
        'jsonrpc' => '2.0',
        'method' => 'hello',
        'params' => { 'name' => 'test', 'version' => '1.0', 'agent' => 'cli', 'pid' => 123 },
        'id' => 1
      }

      response = server.send(:handle_hello, request, context)

      assert response[:error], "Hello should fail without token: #{response.inspect}"
      assert_equal(-32_001, response[:error][:code])
      refute context.identified?
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
      SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, original_token)
    end
  end

  def test_handle_hello_without_token_when_not_required
    # When AUTH_TOKEN is not set, hello should work without token
    original_token = SupexRuntime::BridgeServer::AUTH_TOKEN
    SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
    SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, nil)

    begin
      server = SupexRuntime::BridgeServer.new(port: 0)
      context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: nil)
      request = {
        'jsonrpc' => '2.0',
        'method' => 'hello',
        'params' => { 'name' => 'test', 'version' => '1.0', 'agent' => 'cli', 'pid' => 123 },
        'id' => 1
      }

      response = server.send(:handle_hello, request, context)

      assert response[:result][:success], "Hello should succeed without token when not required"
      assert context.identified?
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
      SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, original_token)
    end
  end

  # ==========================================================================
  # handle_ping tests (unit)
  # ==========================================================================

  def test_handle_ping
    server = SupexRuntime::BridgeServer.new(port: 0)
    request = { 'jsonrpc' => '2.0', 'method' => 'ping', 'id' => 1 }

    response = server.send(:handle_ping, request)

    assert_equal 'ok', response[:result][:status]
    assert response[:result][:version]
  end

  # ==========================================================================
  # require_identification_error tests
  # ==========================================================================

  def test_require_identification_error
    server = SupexRuntime::BridgeServer.new(port: 0)
    request = { 'jsonrpc' => '2.0', 'id' => 1 }

    response = server.send(:require_identification_error, request)

    assert response[:error]
    assert_includes response[:error][:message], 'hello'
  end

  # ==========================================================================
  # execute_tool tests
  # ==========================================================================

  def test_execute_tool_ping
    server = SupexRuntime::BridgeServer.new(port: 0)

    result = server.send(:execute_tool, 'ping', {})

    assert result[:success]
    assert_equal 'connected', result[:status]
  end

  def test_execute_tool_unknown
    server = SupexRuntime::BridgeServer.new(port: 0)

    assert_raises(RuntimeError) do
      server.send(:execute_tool, 'nonexistent_tool', {})
    end
  end

  def test_execute_tool_eval_ruby
    server = SupexRuntime::BridgeServer.new(port: 0)

    result = server.send(:execute_tool, 'eval_ruby', { 'code' => '1 + 1' })

    assert result[:success]
    assert_equal '2', result[:result]
  end

  # ==========================================================================
  # eval_ruby binding isolation tests
  # ==========================================================================

  def test_eval_ruby_binding_isolation
    server = SupexRuntime::BridgeServer.new(port: 0)

    # First eval sets a local variable
    server.send(:eval_ruby, { 'code' => 'isolated_test_var = 42' })

    # Second eval should NOT see the local variable (isolated binding)
    error = assert_raises(RuntimeError) do
      server.send(:eval_ruby, { 'code' => 'isolated_test_var' })
    end

    assert_includes error.message, 'undefined local variable'
  end

  def test_eval_ruby_globals_persist
    server = SupexRuntime::BridgeServer.new(port: 0)

    # Global variables persist (by design - this is expected Ruby behavior)
    server.send(:eval_ruby, { 'code' => '$supex_test_global = 123' })
    result = server.send(:eval_ruby, { 'code' => '$supex_test_global' })

    assert_equal '123', result[:result]
  ensure
    # Clean up global
    $supex_test_global = nil
  end

  def test_eval_ruby_constants_persist
    server = SupexRuntime::BridgeServer.new(port: 0)

    # Constants persist (by design - this is expected Ruby behavior)
    server.send(:eval_ruby, { 'code' => 'SUPEX_TEST_CONST = "test" unless defined?(SUPEX_TEST_CONST)' })
    result = server.send(:eval_ruby, { 'code' => 'SUPEX_TEST_CONST' })

    # result.to_s returns "test" without quotes
    assert_equal 'test', result[:result]
  end

  # ==========================================================================
  # Server lifecycle tests (integration)
  # ==========================================================================

  def test_start_stop_lifecycle
    @server = SupexRuntime::BridgeServer.new(port: 0)

    refute @server.running?

    @server.start
    assert @server.running?

    @server.stop
    refute @server.running?
  end

  def test_start_creates_timer
    @server = SupexRuntime::BridgeServer.new(port: 0)

    @server.start

    refute UI.timers.empty?, 'Timer should be registered'
  end

  def test_start_idempotent
    @server = SupexRuntime::BridgeServer.new(port: 0)

    @server.start
    timer_count = UI.timers.count

    @server.start # Second start should be no-op

    assert_equal timer_count, UI.timers.count, 'Should not create additional timers'
  end

  def test_stop_removes_timer
    @server = SupexRuntime::BridgeServer.new(port: 0)
    @server.start

    refute UI.timers.empty?

    @server.stop

    assert UI.timers.empty?, 'Timer should be removed after stop'
  end

  # ==========================================================================
  # Non-loopback guard tests
  # ==========================================================================

  def test_loopback_address_detection
    server = SupexRuntime::BridgeServer.new(port: 0)

    assert server.send(:loopback_address?, '127.0.0.1')
    assert server.send(:loopback_address?, 'localhost')
    assert server.send(:loopback_address?, '::1')
    refute server.send(:loopback_address?, '0.0.0.0')
    refute server.send(:loopback_address?, '192.168.1.1')
  end

  def test_start_fails_on_non_loopback_without_allow_remote
    original_allow = SupexRuntime::BridgeServer::ALLOW_REMOTE
    SupexRuntime::BridgeServer.send(:remove_const, :ALLOW_REMOTE)
    SupexRuntime::BridgeServer.const_set(:ALLOW_REMOTE, false)

    begin
      @server = SupexRuntime::BridgeServer.new(port: 0, host: '0.0.0.0')

      @server.start

      refute @server.running?, 'Server should not start on non-loopback without ALLOW_REMOTE'
      output = SupexRuntime::Utils.console_output.join("\n")
      assert_includes output, 'requires SUPEX_ALLOW_REMOTE=1'
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :ALLOW_REMOTE)
      SupexRuntime::BridgeServer.const_set(:ALLOW_REMOTE, original_allow)
    end
  end

  def test_start_succeeds_on_non_loopback_with_allow_remote
    original_allow = SupexRuntime::BridgeServer::ALLOW_REMOTE
    SupexRuntime::BridgeServer.send(:remove_const, :ALLOW_REMOTE)
    SupexRuntime::BridgeServer.const_set(:ALLOW_REMOTE, true)

    begin
      @server = SupexRuntime::BridgeServer.new(port: 0, host: '0.0.0.0')

      @server.start

      assert @server.running?, 'Server should start on non-loopback with ALLOW_REMOTE=1'
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :ALLOW_REMOTE)
      SupexRuntime::BridgeServer.const_set(:ALLOW_REMOTE, original_allow)
    end
  end

  def test_start_warns_on_non_loopback_without_token
    original_allow = SupexRuntime::BridgeServer::ALLOW_REMOTE
    original_token = SupexRuntime::BridgeServer::AUTH_TOKEN
    SupexRuntime::BridgeServer.send(:remove_const, :ALLOW_REMOTE)
    SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
    SupexRuntime::BridgeServer.const_set(:ALLOW_REMOTE, true)
    SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, nil)

    begin
      @server = SupexRuntime::BridgeServer.new(port: 0, host: '0.0.0.0')

      @server.start

      assert @server.running?
      output = SupexRuntime::Utils.console_output.join("\n")
      assert_includes output, 'WARNING'
      assert_includes output, 'insecure'
    ensure
      SupexRuntime::BridgeServer.send(:remove_const, :ALLOW_REMOTE)
      SupexRuntime::BridgeServer.send(:remove_const, :AUTH_TOKEN)
      SupexRuntime::BridgeServer.const_set(:ALLOW_REMOTE, original_allow)
      SupexRuntime::BridgeServer.const_set(:AUTH_TOKEN, original_token)
    end
  end

  # ==========================================================================
  # Integration tests (real TCP)
  # ==========================================================================

  def test_hello_handshake_integration
    @server = SupexRuntime::BridgeServer.new(port: 0)
    @server.start
    port = @server.instance_variable_get(:@server).addr[1]

    # Trigger request handling
    client_thread = Thread.new do
      client = MockBridgeClient.new(port: port)
      client.send_hello
    end

    # Give server time to accept
    sleep 0.05
    UI.timers.values.first[:block].call

    response = client_thread.value
    assert response['result']['success'], "Hello should succeed: #{response.inspect}"
  end

  def test_ping_requires_hello_integration
    @server = SupexRuntime::BridgeServer.new(port: 0)
    @server.start
    port = @server.instance_variable_get(:@server).addr[1]

    client_thread = Thread.new do
      client = MockBridgeClient.new(port: port)
      client.send_ping # Without hello first
    end

    sleep 0.05
    UI.timers.values.first[:block].call

    response = client_thread.value
    assert response['error'], "Ping without hello should fail: #{response.inspect}"
    assert_includes response['error']['message'], 'hello'
  end

  # ==========================================================================
  # Framing tests (newline-delimited JSON)
  # ==========================================================================

  def test_complete_json_requires_newline
    @server = SupexRuntime::BridgeServer.new(port: 0)

    # Message without newline should not be complete
    refute @server.send(:complete_json?, '{"test": 1}')
  end

  def test_complete_json_with_newline
    @server = SupexRuntime::BridgeServer.new(port: 0)

    # Message with newline should be complete
    assert @server.send(:complete_json?, "{\"test\": 1}\n")
  end

  def test_complete_json_with_braces_in_string
    @server = SupexRuntime::BridgeServer.new(port: 0)

    # Message with braces in string value should work (newline-based, not brace counting)
    json = "{\"msg\": \"{nested}\"}\n"
    assert @server.send(:complete_json?, json)
  end

  def test_complete_json_with_complex_nested_braces
    @server = SupexRuntime::BridgeServer.new(port: 0)

    # Complex JSON with nested objects - complete when has newline
    json = "{\"outer\": {\"inner\": {\"deep\": \"{value}\"}}}\n"
    assert @server.send(:complete_json?, json)
  end

  def test_incomplete_json_without_trailing_newline
    @server = SupexRuntime::BridgeServer.new(port: 0)

    # Even valid JSON is incomplete without newline
    json = '{"valid": true}'
    refute @server.send(:complete_json?, json)
  end
end
