# frozen_string_literal: true

# Plane utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  module Geom
    # Utilities for working with planes.
    #
    # A plane can be expressed as:
    # - Array of [point, vector] (Point3d and Vector3d)
    # - Array of 4 Floats [a, b, c, d] (plane equation coefficients)
    #
    # SketchUp's API accepts both formats, and so does this module.
    module Plane
      extend self

      # Get the unit normal vector for a plane.
      #
      # @param plane [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @return [Geom::Vector3d] normalized normal vector
      #
      # @example
      #   normal = SupexStdlib::Geom::Plane.normal([ORIGIN, Z_AXIS])
      def normal(plane)
        raise ArgumentError, "Object doesn't represent a plane." unless valid?(plane)

        return plane[1].normalize if plane.size == 2

        a, b, c = plane
        ::Geom::Vector3d.new(a, b, c).normalize
      end

      # Find an arbitrary point on the plane.
      #
      # @param plane [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @return [Geom::Point3d] a point lying on the plane
      #
      # @example
      #   pt = SupexStdlib::Geom::Plane.point([1, 0, 0, -5])  # x = 5 plane
      def point(plane)
        raise ArgumentError, "Object doesn't represent a plane." unless valid?(plane)

        return plane[0] if plane.size == 2

        a, b, c, d = plane
        v = ::Geom::Vector3d.new(a, b, c)
        ORIGIN.offset(v, -d)
      end

      # Test if two planes are parallel.
      #
      # @param plane_a [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @param plane_b [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @return [Boolean] true if planes are parallel
      #
      # @example
      #   SupexStdlib::Geom::Plane.parallel?(plane1, plane2)
      def parallel?(plane_a, plane_b)
        raise ArgumentError, "Object 'plane_a' doesn't represent a plane." unless valid?(plane_a)
        raise ArgumentError, "Object 'plane_b' doesn't represent a plane." unless valid?(plane_b)

        normal(plane_a).parallel?(normal(plane_b))
      end

      # Test if two planes are the same plane.
      #
      # @param plane_a [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @param plane_b [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @param include_flipped [Boolean] whether flipped planes count as same
      # @return [Boolean] true if planes are the same
      #
      # @example
      #   SupexStdlib::Geom::Plane.same?(plane1, plane2, true)
      def same?(plane_a, plane_b, include_flipped = false)
        raise ArgumentError, "Object 'plane_a' doesn't represent a plane." unless valid?(plane_a)
        raise ArgumentError, "Object 'plane_b' doesn't represent a plane." unless valid?(plane_b)

        return false unless point(plane_a).on_plane?(plane_b)
        return false unless parallel?(plane_a, plane_b)

        include_flipped || normal(plane_a).samedirection?(normal(plane_b))
      end

      # Transform a plane by a transformation.
      #
      # @param plane [Array(Geom::Point3d, Geom::Vector3d), Array(Float, Float, Float, Float)]
      # @param transformation [Geom::Transformation]
      # @return [Array(Geom::Point3d, Geom::Vector3d)] transformed plane
      #
      # @example
      #   new_plane = SupexStdlib::Geom::Plane.transform(plane, tr)
      def transform(plane, transformation)
        raise ArgumentError, "Object doesn't represent a plane." unless valid?(plane)
        raise ArgumentError, 'Requires transformation.' unless transformation.is_a?(::Geom::Transformation)

        [
          point(plane).transform(transformation),
          Vector.transform_as_normal(normal(plane), transformation)
        ]
      end

      # Test if an object represents a valid plane.
      #
      # @param plane [Object] object to test
      # @return [Boolean] true if object represents a plane
      #
      # @example
      #   SupexStdlib::Geom::Plane.valid?([ORIGIN, Z_AXIS])  # => true
      #   SupexStdlib::Geom::Plane.valid?([0, 0, 1, 0])      # => true
      def valid?(plane)
        return false unless plane.is_a?(Array)

        (plane.size == 4 && plane.all? { |e| e.is_a?(Numeric) }) ||
          (plane.size == 2 && valid_point?(plane[0]) && valid_vector?(plane[1]))
      end

      private

      # @param object [Object]
      # @return [Boolean]
      def valid_point?(object)
        object.is_a?(::Geom::Point3d) || (object.is_a?(Array) && object.size == 3)
      end

      # @param object [Object]
      # @return [Boolean]
      def valid_vector?(object)
        object.is_a?(::Geom::Vector3d) || (object.is_a?(Array) && object.size == 3)
      end
    end
  end
end
