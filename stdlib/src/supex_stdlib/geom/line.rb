# frozen_string_literal: true

# Line class adapted from tt-lib by Thomas Thomassen (MIT License).
# https://github.com/thomthom/tt-lib

module SupexStdlib
  module Geom
    # Immutable line representation as [point, vector] pair.
    #
    # Extends Array but hides modification methods to ensure immutability.
    # Compatible with SketchUp's line representation (Array of point and vector).
    #
    # @example
    #   line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)
    #   line.direction  # => normalized direction vector
    #   line.valid?     # => true
    class Line < Array
      # Create a new line from a point and direction.
      #
      # @param point [Geom::Point3d] point on the line
      # @param vector [Geom::Vector3d, Geom::Point3d] direction vector or second point
      def initialize(point, vector)
        super()
        push(point)
        push(vector)
      end

      # Get the normalized direction vector of the line.
      #
      # Caches the result for efficiency.
      #
      # @return [Geom::Vector3d] normalized direction
      def direction
        @direction ||= direction_internal
      end

      # Convert to array representation.
      #
      # @return [Array(Geom::Point3d, Geom::Vector3d)] [point, direction]
      def to_a
        [at(0).clone, direction]
      end

      # Check if the line data is valid.
      #
      # @return [Boolean] true if line contains valid point and vector/point
      def valid?
        valid_point3d?(at(0)) && (valid_point3d?(at(1)) || valid_vector3d?(at(1)))
      end

      # @return [String] string representation
      def inspect
        "#{self.class.name}#{super}"
      end

      # Hide Array modification methods to ensure immutability
      private :push, :<<, :pop, :shift, :unshift, :[]=, :concat
      private :delete, :delete_at, :delete_if, :drop, :drop_while, :fill
      if method_defined?(:collect!)
        private :collect!, :compact!, :flatten!, :map!, :reject!, :reverse!,
                :rotate!, :select!, :shuffle!, :slice!, :sort!, :sort_by!, :uniq!
      end

      # Hide SketchUp Array extensions that don't make sense for Line
      if method_defined?(:x)
        private :x, :y, :z
        private :cross, :dot
        private :distance, :distance_to_line, :distance_to_plane
        private :offset, :vector_to
        private :normalize, :normalize!
        private :on_line?, :on_plane?
        private :offset!, :transform!
      end

      private

      # @return [Geom::Vector3d]
      def direction_internal
        second = at(1)
        if second.is_a?(::Geom::Vector3d)
          second.normalize
        elsif second.is_a?(Array) && second.size == 3
          ::Geom::Vector3d.new(second).normalize
        else
          # Assume second is a point, compute vector from first to second
          at(0).vector_to(second).normalize
        end
      end

      # @param object [Object]
      # @return [Boolean]
      def valid_point3d?(object)
        object.is_a?(::Geom::Point3d) || valid_triple?(object)
      end

      # @param object [Object]
      # @return [Boolean]
      def valid_vector3d?(object)
        object.is_a?(::Geom::Vector3d) || valid_triple?(object)
      end

      # @param object [Object]
      # @return [Boolean]
      def valid_triple?(object)
        object.is_a?(Array) && object.size == 3 && object.all? { |item| item.is_a?(Numeric) }
      end
    end
  end
end
