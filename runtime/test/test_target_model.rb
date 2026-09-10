# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/bridge_server'
require 'tmpdir'

class TestTargetModel < Minitest::Test
  def setup
    Sketchup.reset_mocks
    SupexRuntime::Utils.clear_console_output
    @dir = Dir.mktmpdir('supex-target-model')
    @model_path = File.join(@dir, 'house.skp')
    File.write(@model_path, 'skp')
    @other_path = File.join(@dir, 'other.skp')
    File.write(@other_path, 'skp')
  end

  def teardown
    FileUtils.rm_rf(@dir)
    Sketchup.reset_mocks
  end

  def open_model(path)
    title = path ? File.basename(path, '.skp') : 'Untitled'
    Sketchup.mock_model = MockModel.new(path: path, title: title)
  end

  # ==========================================================================
  # enforce!
  # ==========================================================================

  def test_enforce_without_guard_returns_args_unchanged
    args = { 'code' => '1 + 1' }

    assert_same args, SupexRuntime::TargetModel.enforce!(args)
    assert_nil SupexRuntime::TargetModel.enforce!(nil)
  end

  def test_enforce_strips_guard_when_model_matches
    open_model(@model_path)

    rest = SupexRuntime::TargetModel.enforce!({ 'code' => '1', 'expected_model_path' => @model_path })

    assert_equal({ 'code' => '1' }, rest)
  end

  def test_enforce_accepts_unnormalized_path_to_same_file
    open_model(@model_path)
    unnormalized = File.join(@dir, '.', 'house.skp')

    rest = SupexRuntime::TargetModel.enforce!({ 'expected_model_path' => unnormalized })

    assert_empty rest
  end

  def test_enforce_ignores_empty_guard
    open_model(@other_path)

    rest = SupexRuntime::TargetModel.enforce!({ 'code' => '1', 'expected_model_path' => '' })

    assert_equal({ 'code' => '1' }, rest)
  end

  def test_enforce_refuses_other_document
    open_model(@other_path)

    error = assert_raises(SupexRuntime::TargetModel::MismatchError) do
      SupexRuntime::TargetModel.enforce!({ 'expected_model_path' => @model_path })
    end

    assert_includes error.message, @model_path
    assert_includes error.message, @other_path
    assert_equal 'wrong_model', error.data[:error_type]
    assert_equal @model_path, error.data[:expected_model_path]
    assert_equal @other_path, error.data[:active_model_path]
    assert_equal 'other', error.data[:active_model_title]
  end

  def test_enforce_refuses_same_basename_in_another_directory
    other_dir = File.join(@dir, 'copy')
    FileUtils.mkdir_p(other_dir)
    copy = File.join(other_dir, 'house.skp')
    File.write(copy, 'skp')
    open_model(copy)

    assert_raises(SupexRuntime::TargetModel::MismatchError) do
      SupexRuntime::TargetModel.enforce!({ 'expected_model_path' => @model_path })
    end
  end

  def test_enforce_refuses_unsaved_model
    open_model(nil)

    error = assert_raises(SupexRuntime::TargetModel::MismatchError) do
      SupexRuntime::TargetModel.enforce!({ 'expected_model_path' => @model_path })
    end

    assert_includes error.message, 'unsaved'
    assert_nil error.data[:active_model_path]
  end

  def test_enforce_refuses_when_no_model_is_open
    Sketchup.force_no_model = true

    error = assert_raises(SupexRuntime::TargetModel::MismatchError) do
      SupexRuntime::TargetModel.enforce!({ 'expected_model_path' => @model_path })
    end

    assert_includes error.message, 'no model is open'
  end

  # ==========================================================================
  # Bridge integration: the guard runs before the tool
  # ==========================================================================

  def tool_call(arguments)
    { 'jsonrpc' => '2.0', 'method' => 'tools/call', 'id' => 7,
      'params' => { 'name' => 'eval_ruby', 'arguments' => arguments } }
  end

  def test_handle_tool_call_runs_tool_when_model_matches
    open_model(@model_path)
    server = SupexRuntime::BridgeServer.new(port: 0)
    context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: { 'name' => 'test' })

    response = server.send(:handle_tool_call, tool_call({ 'code' => '2 + 2', 'expected_model_path' => @model_path }),
                           context)

    assert_equal '4', response[:result][:result]
  end

  def test_handle_tool_call_refuses_other_document_before_running
    open_model(@other_path)
    server = SupexRuntime::BridgeServer.new(port: 0)
    context = SupexRuntime::BridgeServer::ConnectionContext.new(client_info: { 'name' => 'test' })
    $target_model_test_ran = false # rubocop:disable Style/GlobalVars

    response = server.send(:handle_tool_call,
                           tool_call({ 'code' => '$target_model_test_ran = true',
                                       'expected_model_path' => @model_path }),
                           context)

    refute $target_model_test_ran, 'tool must not run against the wrong document' # rubocop:disable Style/GlobalVars
    assert_equal 7, response[:id]
    assert_equal(-32_603, response[:error][:code])
    assert_includes response[:error][:message], 'refusing to run'
    assert_equal 'wrong_model', response[:error][:data][:error_type]
    assert_equal @other_path, response[:error][:data][:active_model_path]
  end

  def test_model_info_reports_path
    open_model(@model_path)
    server = SupexRuntime::BridgeServer.new(port: 0)

    info = server.send(:execute_tool, 'get_model_info', {})

    assert_equal @model_path, info[:path]
  end

  def test_model_info_path_is_nil_for_unsaved_model
    open_model(nil)
    server = SupexRuntime::BridgeServer.new(port: 0)

    assert_nil server.send(:execute_tool, 'get_model_info', {})[:path]
  end
end
