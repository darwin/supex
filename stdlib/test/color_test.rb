# frozen_string_literal: true

require_relative 'test_helper'

class ColorTest < Minitest::Test
  # Module existence tests

  def test_module_exists
    assert defined?(SupexStdlib::Color)
  end

  # grayscale? tests

  def test_grayscale_with_gray
    color = Sketchup::Color.new(128, 128, 128)

    assert SupexStdlib::Color.grayscale?(color)
  end

  def test_grayscale_with_white
    color = Sketchup::Color.new(255, 255, 255)

    assert SupexStdlib::Color.grayscale?(color)
  end

  def test_grayscale_with_black
    color = Sketchup::Color.new(0, 0, 0)

    assert SupexStdlib::Color.grayscale?(color)
  end

  def test_grayscale_with_red
    color = Sketchup::Color.new(255, 0, 0)

    refute SupexStdlib::Color.grayscale?(color)
  end

  def test_grayscale_with_color
    color = Sketchup::Color.new(100, 150, 200)

    refute SupexStdlib::Color.grayscale?(color)
  end

  # luminance tests

  def test_luminance_black
    color = Sketchup::Color.new(0, 0, 0)

    assert_equal 0, SupexStdlib::Color.luminance(color)
  end

  def test_luminance_white
    color = Sketchup::Color.new(255, 255, 255)

    assert_equal 255, SupexStdlib::Color.luminance(color)
  end

  def test_luminance_gray
    color = Sketchup::Color.new(128, 128, 128)

    assert_equal 128, SupexStdlib::Color.luminance(color)
  end

  def test_luminance_red
    color = Sketchup::Color.new(255, 0, 0)
    # 255 * 0.299 = 76.245
    expected = 76

    assert_equal expected, SupexStdlib::Color.luminance(color)
  end

  def test_luminance_green
    color = Sketchup::Color.new(0, 255, 0)
    # 255 * 0.587 = 149.685
    expected = 149

    assert_equal expected, SupexStdlib::Color.luminance(color)
  end

  def test_luminance_blue
    color = Sketchup::Color.new(0, 0, 255)
    # 255 * 0.114 = 29.07
    expected = 29

    assert_equal expected, SupexStdlib::Color.luminance(color)
  end

  # dark? tests

  def test_dark_with_black
    color = Sketchup::Color.new(0, 0, 0)

    assert SupexStdlib::Color.dark?(color)
  end

  def test_dark_with_white
    color = Sketchup::Color.new(255, 255, 255)

    refute SupexStdlib::Color.dark?(color)
  end

  def test_dark_with_dark_gray
    color = Sketchup::Color.new(50, 50, 50)

    assert SupexStdlib::Color.dark?(color)
  end

  def test_dark_with_custom_threshold
    color = Sketchup::Color.new(200, 200, 200)

    # Should be dark with high threshold
    assert SupexStdlib::Color.dark?(color, 250)
    # Should not be dark with low threshold
    refute SupexStdlib::Color.dark?(color, 100)
  end

  # light? tests

  def test_light_with_white
    color = Sketchup::Color.new(255, 255, 255)

    assert SupexStdlib::Color.light?(color)
  end

  def test_light_with_black
    color = Sketchup::Color.new(0, 0, 0)

    refute SupexStdlib::Color.light?(color)
  end

  # contrast_color tests

  def test_contrast_color_for_dark
    dark = Sketchup::Color.new(0, 0, 0)

    assert_equal [255, 255, 255], SupexStdlib::Color.contrast_color(dark)
  end

  def test_contrast_color_for_light
    light = Sketchup::Color.new(255, 255, 255)

    assert_equal [0, 0, 0], SupexStdlib::Color.contrast_color(light)
  end

  # to_grayscale tests

  def test_to_grayscale
    color = Sketchup::Color.new(255, 0, 0)
    expected = 76 # luminance of pure red

    result = SupexStdlib::Color.to_grayscale(color)

    assert_equal [expected, expected, expected], result
  end

  # components tests

  def test_components
    color = Sketchup::Color.new(100, 150, 200, 128)

    result = SupexStdlib::Color.components(color)

    assert_equal 100, result[:r]
    assert_equal 150, result[:g]
    assert_equal 200, result[:b]
    assert_equal 128, result[:a]
  end

  # to_hex tests

  def test_to_hex_red
    color = Sketchup::Color.new(255, 0, 0)

    assert_equal '#FF0000', SupexStdlib::Color.to_hex(color)
  end

  def test_to_hex_green
    color = Sketchup::Color.new(0, 255, 0)

    assert_equal '#00FF00', SupexStdlib::Color.to_hex(color)
  end

  def test_to_hex_with_alpha
    color = Sketchup::Color.new(255, 128, 0, 128)

    assert_equal '#FF8000', SupexStdlib::Color.to_hex(color, false)
    assert_equal '#FF800080', SupexStdlib::Color.to_hex(color, true)
  end

  def test_to_hex_black
    color = Sketchup::Color.new(0, 0, 0)

    assert_equal '#000000', SupexStdlib::Color.to_hex(color)
  end

  def test_to_hex_white
    color = Sketchup::Color.new(255, 255, 255)

    assert_equal '#FFFFFF', SupexStdlib::Color.to_hex(color)
  end
end
