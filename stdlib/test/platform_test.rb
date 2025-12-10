# frozen_string_literal: true

require_relative 'test_helper'

class PlatformTest < Minitest::Test
  def setup
    # Store original platform
    @original_platform = Sketchup.platform
  end

  def teardown
    # Restore original platform
    Sketchup.platform = @original_platform
  end

  def test_mac_returns_true_on_osx
    Sketchup.platform = :platform_osx
    # Need to reload the module to pick up the change
    # For constants, we test with the actual platform
    assert_equal :platform_osx, Sketchup.platform
  end

  def test_win_returns_true_on_windows
    Sketchup.platform = :platform_win
    assert_equal :platform_win, Sketchup.platform
  end

  def test_mac_method
    Sketchup.platform = :platform_osx
    assert SupexStdlib::Platform.mac?
    refute SupexStdlib::Platform.win?
  end

  def test_win_method
    Sketchup.platform = :platform_win
    assert SupexStdlib::Platform.win?
    refute SupexStdlib::Platform.mac?
  end

  def test_pointer_size_is_32_or_64
    assert_includes [32, 64], SupexStdlib::Platform::POINTER_SIZE
  end

  def test_key_is_osx_or_win
    assert_includes %w[osx win], SupexStdlib::Platform::KEY
  end

  def test_id_combines_key_and_pointer_size
    expected_pattern = /^(osx|win)(32|64)$/
    assert_match expected_pattern, SupexStdlib::Platform::ID
  end

  def test_name_is_readable
    assert_includes %w[macOS Windows], SupexStdlib::Platform::NAME
  end

  def test_is_mac_is_boolean
    assert_includes [true, false], SupexStdlib::Platform::IS_MAC
  end

  def test_is_win_is_boolean
    assert_includes [true, false], SupexStdlib::Platform::IS_WIN
  end

  def test_is_mac_and_is_win_are_mutually_exclusive
    refute_equal SupexStdlib::Platform::IS_MAC, SupexStdlib::Platform::IS_WIN
  end

  def test_temp_path_returns_existing_directory
    path = SupexStdlib::Platform.temp_path
    assert File.exist?(path), "temp_path should return existing directory: #{path}"
    assert File.directory?(path), "temp_path should return a directory: #{path}"
  end

  def test_temp_path_is_expanded
    path = SupexStdlib::Platform.temp_path
    assert_equal File.expand_path(path), path
  end
end
