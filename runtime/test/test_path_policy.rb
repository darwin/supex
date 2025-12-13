# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/path_policy'

class TestPathPolicy < Minitest::Test
  def setup
    # Store original constants
    @original_allowed_roots = SupexRuntime::PathPolicy::ALLOWED_ROOTS.dup
    @original_project_root = SupexRuntime::PathPolicy::PROJECT_ROOT
  end

  def teardown
    # Restore original constants
    restore_constant(:ALLOWED_ROOTS, @original_allowed_roots)
    restore_constant(:PROJECT_ROOT, @original_project_root)
  end

  # ==========================================================================
  # Basic validation tests
  # ==========================================================================

  def test_path_in_default_tmp_is_allowed
    tmp_path = File.join(SupexRuntime::PathPolicy::DEFAULT_TMP, 'test.rb')

    # Should not raise
    SupexRuntime::PathPolicy.validate!(tmp_path)
  end

  def test_path_outside_allowed_roots_raises
    set_constant(:ALLOWED_ROOTS, [])
    set_constant(:PROJECT_ROOT, nil)

    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/etc/passwd')
    end
  end

  def test_path_in_project_root_is_allowed
    project_root = '/tmp/test_project'
    set_constant(:PROJECT_ROOT, project_root)

    # Should not raise
    SupexRuntime::PathPolicy.validate!(File.join(project_root, 'script.rb'))
  end

  def test_path_in_allowed_roots_is_allowed
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])

    # Should not raise
    SupexRuntime::PathPolicy.validate!('/tmp/allowed/test.rb')
  end

  # ==========================================================================
  # Traversal attack tests
  # ==========================================================================

  def test_traversal_attack_is_blocked
    set_constant(:ALLOWED_ROOTS, ['/tmp/allowed'])
    set_constant(:PROJECT_ROOT, nil)

    # Attempt traversal
    assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/tmp/allowed/../../../etc/passwd')
    end
  end

  def test_traversal_within_allowed_root_works
    tmp_path = SupexRuntime::PathPolicy::DEFAULT_TMP
    path_with_dots = File.join(tmp_path, 'subdir', '..', 'test.rb')

    # Should not raise - resolves to within DEFAULT_TMP
    SupexRuntime::PathPolicy.validate!(path_with_dots)
  end

  # ==========================================================================
  # Allow all mode
  # ==========================================================================

  def test_allow_all_mode
    set_constant(:ALLOWED_ROOTS, ['*'])
    set_constant(:PROJECT_ROOT, nil)

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
    set_constant(:PROJECT_ROOT, nil)

    error = assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
      SupexRuntime::PathPolicy.validate!('/etc/passwd', operation: 'eval_ruby_file')
    end

    assert_includes error.message, 'eval_ruby_file'
    assert_includes error.message, '/etc/passwd'
  end

  # ==========================================================================
  # allowed_roots method tests
  # ==========================================================================

  def test_allowed_roots_includes_default_tmp
    roots = SupexRuntime::PathPolicy.allowed_roots

    assert_includes roots, File.expand_path(SupexRuntime::PathPolicy::DEFAULT_TMP)
  end

  def test_allowed_roots_includes_project_root
    project_root = '/tmp/my_project'
    set_constant(:PROJECT_ROOT, project_root)

    roots = SupexRuntime::PathPolicy.allowed_roots

    assert_includes roots, project_root
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
