# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/repl_server'

class TestREPLServer < Minitest::Test
  def setup
    UI.clear_timers
    UI.reset_ui_mocks
    SupexRuntime::Utils.clear_console_output

    # Ensure SNIPPETS_DIR exists for testing
    @snippets_dir = SupexRuntime::REPLServer::SNIPPETS_DIR
    FileUtils.mkdir_p(@snippets_dir)
  end

  def teardown
    UI.clear_timers
    SupexRuntime::Utils.clear_console_output

    # Clean up test session directories
    Dir.glob(File.join(@snippets_dir, 'stest-*')).each do |dir|
      FileUtils.rm_rf(dir)
    end
  end

  # ==========================================================================
  # sanitize_pid tests
  # ==========================================================================

  def test_sanitize_pid_valid_numeric
    server = SupexRuntime::REPLServer.new(port: 0)

    assert_equal '12345', server.send(:sanitize_pid, '12345')
    assert_equal '1', server.send(:sanitize_pid, '1')
    assert_equal '9999999999', server.send(:sanitize_pid, '9999999999') # 10 digits
  end

  def test_sanitize_pid_integer_input
    server = SupexRuntime::REPLServer.new(port: 0)

    assert_equal '42', server.send(:sanitize_pid, 42)
  end

  def test_sanitize_pid_rejects_path_traversal
    server = SupexRuntime::REPLServer.new(port: 0)

    result = server.send(:sanitize_pid, '../../etc')

    assert_equal Process.pid.to_s, result
  end

  def test_sanitize_pid_rejects_non_numeric
    server = SupexRuntime::REPLServer.new(port: 0)

    result = server.send(:sanitize_pid, 'abc')

    assert_equal Process.pid.to_s, result
  end

  def test_sanitize_pid_rejects_too_long
    server = SupexRuntime::REPLServer.new(port: 0)

    result = server.send(:sanitize_pid, '12345678901') # 11 digits

    assert_equal Process.pid.to_s, result
  end

  def test_sanitize_pid_nil_fallback
    server = SupexRuntime::REPLServer.new(port: 0)

    # nil.to_s is "" which is empty, should fallback without warning
    result = server.send(:sanitize_pid, nil)

    assert_equal Process.pid.to_s, result
  end

  def test_sanitize_pid_rejects_mixed_content
    server = SupexRuntime::REPLServer.new(port: 0)

    result = server.send(:sanitize_pid, '123/456')

    assert_equal Process.pid.to_s, result
  end

  def test_sanitize_pid_logs_warning_for_invalid
    server = SupexRuntime::REPLServer.new(port: 0)
    SupexRuntime::Utils.clear_console_output

    server.send(:sanitize_pid, '../../etc')

    output = SupexRuntime::Utils.console_output.join("\n")
    assert_includes output, 'WARNING'
    assert_includes output, 'Invalid PID'
  end

  def test_sanitize_pid_no_warning_for_nil
    server = SupexRuntime::REPLServer.new(port: 0)
    SupexRuntime::Utils.clear_console_output

    server.send(:sanitize_pid, nil)

    output = SupexRuntime::Utils.console_output.join("\n")
    refute_includes output, 'WARNING'
  end

  # ==========================================================================
  # handle_hello session path tests
  # ==========================================================================

  def test_handle_hello_creates_session_dir
    server = SupexRuntime::REPLServer.new(port: 0)
    client = SupexRuntime::REPLServer::ClientConnection.new(
      socket: nil, client_info: nil, session_dir: nil, snippet_counter: 0
    )
    request = {
      'jsonrpc' => '2.0',
      'method' => 'hello',
      'params' => { 'name' => 'test', 'pid' => '12345' },
      'id' => 1
    }

    response = server.send(:handle_hello, request, client)

    assert response[:result][:success], "Hello should succeed: #{response.inspect}"
    assert client.session_dir
    assert Dir.exist?(client.session_dir)
  ensure
    FileUtils.rm_rf(client.session_dir) if client&.session_dir
  end

  def test_handle_hello_sanitizes_traversal_pid
    server = SupexRuntime::REPLServer.new(port: 0)
    client = SupexRuntime::REPLServer::ClientConnection.new(
      socket: nil, client_info: nil, session_dir: nil, snippet_counter: 0
    )
    request = {
      'jsonrpc' => '2.0',
      'method' => 'hello',
      'params' => { 'name' => 'test', 'pid' => '../../etc' },
      'id' => 1
    }

    response = server.send(:handle_hello, request, client)

    # Should succeed with fallback PID
    assert response[:result][:success], "Hello should succeed with sanitized PID: #{response.inspect}"
    # Session dir should be within snippets root
    canonical_snippets = File.realpath(@snippets_dir)
    assert client.session_dir.start_with?("#{canonical_snippets}/")
  ensure
    FileUtils.rm_rf(client.session_dir) if client&.session_dir
  end

  def test_handle_hello_session_within_snippets_root
    server = SupexRuntime::REPLServer.new(port: 0)
    client = SupexRuntime::REPLServer::ClientConnection.new(
      socket: nil, client_info: nil, session_dir: nil, snippet_counter: 0
    )
    request = {
      'jsonrpc' => '2.0',
      'method' => 'hello',
      'params' => { 'name' => 'test', 'pid' => '999' },
      'id' => 1
    }

    response = server.send(:handle_hello, request, client)

    assert response[:result][:success]
    canonical_snippets = File.realpath(@snippets_dir)
    canonical_session = File.realpath(client.session_dir)
    assert canonical_session.start_with?("#{canonical_snippets}/"),
           "Session dir should be within snippets root: #{canonical_session}"
  ensure
    FileUtils.rm_rf(client.session_dir) if client&.session_dir
  end
end
