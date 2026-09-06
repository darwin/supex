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
    Dir.mktmpdir('root1') do |root1|
      Dir.mktmpdir('root2') do |root2|
        set_constant(:ALLOWED_ROOTS, [root1, root2])

        roots = SupexRuntime::PathPolicy.allowed_roots

        # Roots are canonicalized (symlinks resolved)
        assert_includes roots, File.realpath(root1)
        assert_includes roots, File.realpath(root2)
      end
    end
  end

  def test_allowed_roots_includes_workspace_when_provided
    Dir.mktmpdir('allowed') do |allowed_dir|
      Dir.mktmpdir('workspace') do |workspace_dir|
        set_constant(:ALLOWED_ROOTS, [allowed_dir])

        roots = SupexRuntime::PathPolicy.allowed_roots(workspace: workspace_dir)

        assert_includes roots, File.realpath(allowed_dir)
        assert_includes roots, File.realpath(workspace_dir)
      end
    end
  end

  def test_allowed_roots_ignores_empty_workspace
    Dir.mktmpdir('allowed') do |allowed_dir|
      set_constant(:ALLOWED_ROOTS, [allowed_dir])

      roots = SupexRuntime::PathPolicy.allowed_roots(workspace: '')

      assert_includes roots, File.realpath(allowed_dir)
      assert_equal 1, roots.length
    end
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

  # ==========================================================================
  # Symlink hardening tests
  # ==========================================================================

  def test_symlinked_parent_escapes_are_blocked
    set_constant(:ALLOWED_ROOTS, [])

    # Create a real directory and a symlink pointing outside allowed roots
    Dir.mktmpdir('allowed') do |allowed_dir|
      Dir.mktmpdir('outside') do |outside_dir|
        symlink_path = File.join(allowed_dir, 'escape_link')
        File.symlink(outside_dir, symlink_path)

        # Workspace is the allowed dir
        # Writing to escape_link/file.txt should resolve through the symlink
        # to outside_dir/file.txt which is NOT within allowed_dir
        assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
          SupexRuntime::PathPolicy.validate!(
            File.join(symlink_path, 'file.txt'),
            operation: 'write_test',
            workspace: allowed_dir
          )
        end
      end
    end
  end

  def test_symlinked_parent_within_allowed_root_works
    set_constant(:ALLOWED_ROOTS, [])

    Dir.mktmpdir('workspace') do |workspace_dir|
      # Create a subdirectory and a symlink pointing to it (within workspace)
      real_subdir = File.join(workspace_dir, 'real_sub')
      FileUtils.mkdir_p(real_subdir)
      link_path = File.join(workspace_dir, 'link_sub')
      File.symlink(real_subdir, link_path)

      # Writing via symlink that stays within workspace should be allowed
      SupexRuntime::PathPolicy.validate!(
        File.join(link_path, 'file.txt'),
        operation: 'write_test',
        workspace: workspace_dir
      )
    end
  end

  def test_nonexistent_file_in_real_directory_is_allowed
    set_constant(:ALLOWED_ROOTS, [])

    Dir.mktmpdir('workspace') do |workspace_dir|
      # Non-existing file inside workspace (no symlinks involved)
      SupexRuntime::PathPolicy.validate!(
        File.join(workspace_dir, 'new_file.txt'),
        operation: 'write_test',
        workspace: workspace_dir
      )
    end
  end

  def test_nonexistent_nested_path_resolves_through_ancestor
    set_constant(:ALLOWED_ROOTS, [])

    Dir.mktmpdir('workspace') do |workspace_dir|
      # Deep non-existing path: workspace/a/b/c/file.txt
      # Only workspace exists, but path should resolve correctly
      SupexRuntime::PathPolicy.validate!(
        File.join(workspace_dir, 'a', 'b', 'c', 'file.txt'),
        operation: 'write_test',
        workspace: workspace_dir
      )
    end
  end

  # ==========================================================================
  # Relative path resolution tests
  # ==========================================================================

  def test_relative_path_resolves_against_workspace
    set_constant(:ALLOWED_ROOTS, [])

    Dir.mktmpdir('workspace') do |workspace_dir|
      Dir.mkdir(File.join(workspace_dir, 'src'))
      File.write(File.join(workspace_dir, 'src', 'script.rb'), '')

      Dir.chdir(Dir.tmpdir) do
        resolved = SupexRuntime::PathPolicy.validate!('src/script.rb', workspace: workspace_dir)

        assert_equal File.realpath(File.join(workspace_dir, 'src', 'script.rb')), File.realpath(resolved)
      end
    end
  end

  def test_relative_path_escaping_workspace_raises
    set_constant(:ALLOWED_ROOTS, [])

    Dir.mktmpdir('workspace') do |workspace_dir|
      assert_raises(SupexRuntime::PathPolicy::PathAccessDenied) do
        SupexRuntime::PathPolicy.validate!('../outside.rb', workspace: workspace_dir)
      end
    end
  end

  def test_relative_path_without_workspace_uses_cwd
    set_constant(:ALLOWED_ROOTS, ['*'])

    Dir.mktmpdir('cwd') do |cwd|
      Dir.chdir(cwd) do
        resolved = SupexRuntime::PathPolicy.validate!('file.rb')

        assert_equal File.join(Dir.pwd, 'file.rb'), resolved
      end
    end
  end

  def test_validate_returns_absolute_path_and_nil_for_nil
    set_constant(:ALLOWED_ROOTS, [])

    Dir.mktmpdir('workspace') do |workspace_dir|
      absolute = File.join(workspace_dir, 'a.rb')

      assert_equal absolute, SupexRuntime::PathPolicy.validate!(absolute, workspace: workspace_dir)
      assert_nil SupexRuntime::PathPolicy.validate!(nil, workspace: workspace_dir)
    end
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
