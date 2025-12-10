# frozen_string_literal: true

# Color utilities adapted from tt-lib by Thomas Thomassen (MIT License).
# https://github.com/thomthom/tt-lib
#
# Luminance calculation uses the W3C AERT formula for perceived brightness.
# https://www.w3.org/TR/AERT/#color-contrast

module SupexStdlib
  # Utilities for working with colors.
  #
  # Provides color analysis methods compatible with Sketchup::Color objects.
  module Color
    extend self

    # W3C luminance coefficients (scaled to avoid floats)
    # https://www.w3.org/TR/AERT/#color-contrast
    LUMINANCE_RED   = 299
    LUMINANCE_GREEN = 587
    LUMINANCE_BLUE  = 114
    LUMINANCE_DIVISOR = 1000

    # Test if a color is grayscale.
    #
    # A color is grayscale when red, green, and blue components are equal.
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @return [Boolean]
    #
    # @example
    #   SupexStdlib::Color.grayscale?(Sketchup::Color.new(128, 128, 128))  # => true
    #   SupexStdlib::Color.grayscale?(Sketchup::Color.new(255, 0, 0))      # => false
    def grayscale?(color)
      color.red == color.green && color.green == color.blue
    end

    # Calculate the perceived luminance of a color.
    #
    # Uses the W3C color contrast formula to compute perceived brightness.
    # Returns a value between 0 (black) and 255 (white).
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @return [Integer] luminance value (0-255)
    #
    # @example
    #   SupexStdlib::Color.luminance(Sketchup::Color.new(0, 0, 0))      # => 0
    #   SupexStdlib::Color.luminance(Sketchup::Color.new(255, 255, 255)) # => 255
    def luminance(color)
      ((color.red * LUMINANCE_RED) +
       (color.green * LUMINANCE_GREEN) +
       (color.blue * LUMINANCE_BLUE)) / LUMINANCE_DIVISOR
    end

    # Test if a color is dark (luminance below threshold).
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @param threshold [Integer] luminance threshold (default 128)
    # @return [Boolean]
    #
    # @example
    #   SupexStdlib::Color.dark?(Sketchup::Color.new(50, 50, 50))  # => true
    def dark?(color, threshold = 128)
      luminance(color) < threshold
    end

    # Test if a color is light (luminance at or above threshold).
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @param threshold [Integer] luminance threshold (default 128)
    # @return [Boolean]
    #
    # @example
    #   SupexStdlib::Color.light?(Sketchup::Color.new(200, 200, 200))  # => true
    def light?(color, threshold = 128)
      luminance(color) >= threshold
    end

    # Get an appropriate contrasting color (black or white).
    #
    # Returns white for dark colors and black for light colors.
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @param threshold [Integer] luminance threshold (default 128)
    # @return [Array(Integer, Integer, Integer)] RGB values for contrast color
    #
    # @example
    #   SupexStdlib::Color.contrast_color(dark_color)  # => [255, 255, 255]
    def contrast_color(color, threshold = 128)
      dark?(color, threshold) ? [255, 255, 255] : [0, 0, 0]
    end

    # Convert a color to grayscale.
    #
    # Uses luminance value for all RGB components.
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @return [Array(Integer, Integer, Integer)] RGB values
    #
    # @example
    #   SupexStdlib::Color.to_grayscale(color)  # => [lum, lum, lum]
    def to_grayscale(color)
      lum = luminance(color)
      [lum, lum, lum]
    end

    # Get shortened accessors for color components.
    #
    # @param color [Sketchup::Color, #red, #green, #blue, #alpha]
    # @return [Hash] hash with :r, :g, :b, :a keys
    def components(color)
      {
        r: color.red,
        g: color.green,
        b: color.blue,
        a: color.alpha
      }
    end

    # Convert color to hex string.
    #
    # @param color [Sketchup::Color, #red, #green, #blue]
    # @param include_alpha [Boolean] whether to include alpha channel
    # @return [String] hex color string (e.g., "#FF0000" or "#FF0000FF")
    def to_hex(color, include_alpha = false)
      hex = format('#%02X%02X%02X', color.red, color.green, color.blue)
      hex += format('%02X', color.alpha) if include_alpha
      hex
    end
  end
end
