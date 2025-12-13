# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/supex_runtime/export'

class TestExport < Minitest::Test
  # ==========================================================================
  # Supported formats tests
  # ==========================================================================

  def test_supported_formats_include_skp
    assert_includes SupexRuntime::Export::SUPPORTED_FORMATS, 'skp'
  end

  def test_supported_formats_include_stl
    assert_includes SupexRuntime::Export::SUPPORTED_FORMATS, 'stl'
  end

  def test_supported_formats_include_obj
    assert_includes SupexRuntime::Export::SUPPORTED_FORMATS, 'obj'
  end

  def test_supported_formats_include_image_formats
    assert_includes SupexRuntime::Export::SUPPORTED_FORMATS, 'png'
    assert_includes SupexRuntime::Export::SUPPORTED_FORMATS, 'jpg'
    assert_includes SupexRuntime::Export::SUPPORTED_FORMATS, 'jpeg'
  end

  # ==========================================================================
  # Unsupported format tests
  # ==========================================================================

  def test_unsupported_format_raises_error
    error = assert_raises(RuntimeError) do
      SupexRuntime::Export.export_scene({ 'format' => 'xyz' })
    end
    assert_includes error.message, 'Unsupported export format'
    assert_includes error.message, 'xyz'
  end

  def test_empty_format_uses_default_skp
    # Default format is 'skp', which is supported
    result = SupexRuntime::Export.export_scene({})
    assert_equal 'skp', result[:format]
  end

  # ==========================================================================
  # Result format tests
  # ==========================================================================

  def test_result_contains_file_path_key
    result = SupexRuntime::Export.export_scene({ 'format' => 'skp' })
    assert result.key?(:file_path), 'Result should contain :file_path key'
  end

  def test_result_contains_success_key
    result = SupexRuntime::Export.export_scene({ 'format' => 'skp' })
    assert result.key?(:success), 'Result should contain :success key'
    assert_equal true, result[:success]
  end

  def test_result_contains_format_key
    result = SupexRuntime::Export.export_scene({ 'format' => 'skp' })
    assert result.key?(:format), 'Result should contain :format key'
    assert_equal 'skp', result[:format]
  end

  def test_file_path_is_string
    result = SupexRuntime::Export.export_scene({ 'format' => 'skp' })
    assert_kind_of String, result[:file_path]
  end

  def test_file_path_ends_with_format_extension
    result = SupexRuntime::Export.export_scene({ 'format' => 'skp' })
    assert result[:file_path].end_with?('.skp'), 'File path should end with .skp'
  end
end
