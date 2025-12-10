# frozen_string_literal: true

# BoundingBox class adapted from tt-lib by Thomas Thomassen (MIT License).
# https://github.com/thomthom/tt-lib

module SupexStdlib
  module Geom
    # Constants for BoundingBox corner indices.
    #
    # These match the corner indices used by Geom::BoundingBox.corner
    module BoundingBoxConstants
      BOTTOM_FRONT_LEFT  = 0
      BOTTOM_FRONT_RIGHT = 1
      BOTTOM_BACK_RIGHT  = 2
      BOTTOM_BACK_LEFT   = 3

      TOP_FRONT_LEFT  = 4
      TOP_FRONT_RIGHT = 5
      TOP_BACK_RIGHT  = 6
      TOP_BACK_LEFT   = 7
    end

    # Oriented bounding box representation.
    #
    # Unlike SketchUp's native Geom::BoundingBox, this class represents
    # the orientation in model space - the visible bounding box one sees
    # in the viewport.
    #
    # @example Creating from 8 corner points
    #   corners = (0..7).map { |i| native_bb.corner(i) }
    #   bb = SupexStdlib::Geom::BoundingBox.new(corners)
    #   bb.width   # => dimension along X axis
    #   bb.height  # => dimension along Y axis
    #   bb.depth   # => dimension along Z axis
    class BoundingBox
      include BoundingBoxConstants

      # @return [Array<Geom::Point3d>] the corner points (0, 4, or 8 points)
      attr_reader :points

      # Create a new oriented bounding box.
      #
      # @param points [Array<Geom::Point3d>] 0, 4 or 8 corner points
      # @raise [ArgumentError] if points count is not 0, 4, or 8
      #
      # @example Empty bounding box
      #   bb = SupexStdlib::Geom::BoundingBox.new([])
      #
      # @example 2D bounding box (4 points)
      #   bb = SupexStdlib::Geom::BoundingBox.new(four_points)
      #
      # @example 3D bounding box (8 points)
      #   bb = SupexStdlib::Geom::BoundingBox.new(eight_points)
      def initialize(points)
        raise ArgumentError, "Expected 0, 4 or 8 points (#{points.size} given)" unless [0, 4, 8].include?(points.size)

        @points = points
      end

      # Check if the bounding box is empty.
      #
      # @return [Boolean] true if no points defined
      def empty?
        @points.empty?
      end

      # Check if the bounding box is 2D (planar).
      #
      # @return [Boolean] true if 4 points defined
      def is_2d?
        @points.size == 4
      end

      # Check if the bounding box is 3D.
      #
      # @return [Boolean] true if 8 points defined
      def is_3d?
        @points.size == 8
      end

      # Check if the bounding box has area.
      #
      # @return [Boolean] true if both X and Y axes are valid (non-zero)
      def have_area?
        return false if empty?

        x_axis.valid? && y_axis.valid?
      end

      # Check if the bounding box has volume.
      #
      # @return [Boolean] true if all three axes are valid (non-zero)
      def have_volume?
        return false if empty? || is_2d?

        x_axis.valid? && y_axis.valid? && z_axis.valid?
      end

      # Get the width (X dimension).
      #
      # @return [Float] length along X axis
      def width
        return 0.0 if empty?

        x_axis.length
      end

      # Get the height (Y dimension).
      #
      # @return [Float] length along Y axis
      def height
        return 0.0 if empty?

        y_axis.length
      end

      # Get the depth (Z dimension).
      #
      # @return [Float] length along Z axis
      def depth
        return 0.0 if empty? || is_2d?

        z_axis.length
      end

      # Get the origin point (bottom front left corner).
      #
      # @return [Geom::Point3d, nil] origin point or nil if empty
      def origin
        return nil if empty?

        @points[BOTTOM_FRONT_LEFT]
      end

      # Get the X axis vector.
      #
      # @return [Geom::Vector3d] vector from origin to bottom front right
      def x_axis
        return ::Geom::Vector3d.new(0, 0, 0) if empty?

        @points[BOTTOM_FRONT_LEFT].vector_to(@points[BOTTOM_FRONT_RIGHT])
      end

      # Get the Y axis vector.
      #
      # @return [Geom::Vector3d] vector from origin to bottom back left
      def y_axis
        return ::Geom::Vector3d.new(0, 0, 0) if empty?

        @points[BOTTOM_FRONT_LEFT].vector_to(@points[BOTTOM_BACK_LEFT])
      end

      # Get the Z axis vector.
      #
      # @return [Geom::Vector3d] vector from origin to top front left
      def z_axis
        return ::Geom::Vector3d.new(0, 0, 0) if empty? || is_2d?

        @points[BOTTOM_FRONT_LEFT].vector_to(@points[TOP_FRONT_LEFT])
      end

      # Get the center point of the bounding box.
      #
      # @return [Geom::Point3d, nil] center point or nil if empty
      def center
        return nil if empty?

        if is_2d?
          # Center of 4 points
          x = @points.sum(&:x) / 4.0
          y = @points.sum(&:y) / 4.0
          z = @points.sum(&:z) / 4.0
        else
          # Center of 8 points
          x = @points.sum(&:x) / 8.0
          y = @points.sum(&:y) / 8.0
          z = @points.sum(&:z) / 8.0
        end
        ::Geom::Point3d.new(x, y, z)
      end

      # Get the volume of the bounding box.
      #
      # @return [Float] volume (0 for empty or 2D boxes)
      def volume
        return 0.0 unless have_volume?

        width * height * depth
      end

      # Get the area of the bounding box base (XY plane).
      #
      # @return [Float] area (0 for empty boxes)
      def area
        return 0.0 unless have_area?

        width * height
      end

      # Get a specific corner point.
      #
      # @param index [Integer] corner index (0-7)
      # @return [Geom::Point3d, nil] corner point or nil if invalid
      def corner(index)
        @points[index]
      end

      # @return [String] string representation
      def inspect
        "#{self.class.name}(#{@points.size} points)"
      end
    end
  end
end
