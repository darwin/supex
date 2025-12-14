# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/path_policy'

class TestPathPolicy < Minitest::Test
  def setup
    # Store original constants
    @original_allowed_roots = SupexRuntime::PathPolicy::ALLOWED_ROOTS.dup
  end

  def teardown
    # Restore original constants
    restore_constant(:ALLOWED_ROOTS, @original_allowed_roots)
  end

  # ==========================================================================
  # Basic validation tests
  # ==========================================================================

  def test_path_outside_allowed_roots_raises
    set_constant(:ALLOWED_ROOTS, [])

    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/etc/passwd')
    end
  end

  def test_path_in_allowed_roots_is_allowed
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])

    # Should not raise
    SupexRuntime::PathPolicy.validate!('/tmp/allowed/test.rb')
  end

  def test_path_in_workspace_is_allowed
    set_constant(:ALLOWED_ROOTS, [])
    workspace = '/tmp/my_workspace'

    # Should not raise when workspace is provided
    SupexRuntime::PathPolicy.validate!(
      File.join(workspace, 'script.rb'),
      workspace: workspace
    )
  end

  def test_path_outside_workspace_raises
    set_constant(:ALLOWED_ROOTS, [])
    workspace = '/tmp/my_workspace'

    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/etc/passwd', workspace: workspace)
    end
  end

  # ==========================================================================
  # Traversal attack tests
  # ==========================================================================

  def test_traversal_attack_is_blocked
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])

    # Attempt traversal
    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/tmp/allowed/../../../etc/passwd')
    end
  end

  def test_traversal_within_allowed_root_works
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])
    path_with_dots = '/tmp/allowed/subdir/../test.rb'

    # Should not raise - resolves to within allowed root
    SupexRuntime::PathPolicy.validate!(path_with_dots)
  end

  # ==========================================================================
  # Allow all mode
  # ==========================================================================

  def test_allow_all_mode
    set_constant(:ALLOWED_ROOTS, ['*'])

    # Should allow any path
    SupexRuntime::PathPolicy.validate!('/etc/passwd')
    SupexRuntime::PathPolicy.validate!('/some/random/path')
  end

  # ==========================================================================
  # Nil path handling
  # ==========================================================================

  def test_nil_path_is_allowed
    # nil path should not raise (for optional path parameters)
    SupexRuntime::PathPolicy.validate!(nil)
  end

  # ==========================================================================
  # Error message tests
  # ==========================================================================

  def test_error_message_includes_operation
    set_constant(:ALLOWED_ROOTS, [])

    error = assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/etc/passwd', operation: 'eval_ruby_file')
    end

    assert_includes error.message, 'eval_ruby_file'
    assert_includes error.message, '/etc/passwd'
  end

  # ==========================================================================
  # allowed_roots method tests
  # ==========================================================================

  def test_allowed_roots_returns_configured_roots
    set_constant(:ALLOWED_ROOTS, ['/tmp/root1', '/tmp/root2'])

    roots = SupexRuntime::PathPolicy.allowed_roots

    assert_includes roots, '/tmp/root1'
    assert_includes roots, '/tmp/root2'
  end

  def test_allowed_roots_includes_workspace_when_provided
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])
    workspace = '/tmp/my_workspace'

    roots = SupexRuntime::PathPolicy.allowed_roots(workspace: workspace)

    assert_includes roots, '/tmp/allowed'
    assert_includes roots, workspace
  end

  def test_allowed_roots_ignores_empty_workspace
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])

    roots = SupexRuntime::PathPolicy.allowed_roots(workspace: '')

    assert_includes roots, '/tmp/allowed'
    assert_equal 1, roots.length
  end

  # ==========================================================================
  # default_tmp_dir tests
  # ==========================================================================

  def test_default_tmp_dir_returns_workspace_tmp
    workspace = '/tmp/my_project'

    result = SupexRuntime::PathPolicy.default_tmp_dir(workspace)

    assert_equal '/tmp/my_project/.tmp', result
  end

  def test_default_tmp_dir_raises_without_workspace
    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.default_tmp_dir(nil)
    end
  end

  def test_default_tmp_dir_raises_with_empty_workspace
    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.default_tmp_dir('')
    end
  end

  def test_default_tmp_dir_expands_relative_path
    workspace = 'relative/path'

    result = SupexRuntime::PathPolicy.default_tmp_dir(workspace)

    assert result.start_with?('/')
    assert result.end_with?('/.tmp')
  end

  private

  def set_constant(name, value)
    SupexRuntime::PathPolicy.send(:remove_const, name) if SupexRuntime::PathPolicy.const_defined?(name)
    SupexRuntime::PathPolicy.const_set(name, value)
  end

  def restore_constant(name, value)
    SupexRuntime::PathPolicy.send(:remove_const, name) if SupexRuntime::PathPolicy.const_defined?(name)
    SupexRuntime::PathPolicy.const_set(name, value)
  end
end
