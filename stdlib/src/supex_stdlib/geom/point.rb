# frozen_string_literal: true

# Point utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  module Geom
    # Utilities for working with Geom::Point3d objects.
    module Point
      extend self

      # Test if a point lies between two other points on a line segment.
      #
      # @param point [Geom::Point3d] point to test
      # @param boundary_a [Geom::Point3d] first boundary point
      # @param boundary_b [Geom::Point3d] second boundary point
      # @param include_boundaries [Boolean] whether to include boundary points
      # @return [Boolean] true if point is between boundaries
      #
      # @example
      #   SupexStdlib::Geom::Point.between?(ORIGIN, pt1, pt2)
      def between?(point, boundary_a, boundary_b, include_boundaries = true)
        return false unless point.on_line?([boundary_a, boundary_b])

        vector_a = point - boundary_a
        vector_b = point - boundary_b

        # Point is on one of the boundaries
        return include_boundaries if !vector_a.valid? || !vector_b.valid?

        # Point is between if vectors point in opposite directions
        !vector_a.samedirection?(vector_b)
      end

      # Test if a point is in front of a plane (positive side of normal).
      #
      # @param point [Geom::Point3d] point to test
      # @param plane [Array] plane as [point, vector] or [a, b, c, d]
      # @return [Boolean] true when in front, false when behind or on plane
      #
      # @note This method requires Geom::Plane module (Phase 3)
      def front_of_plane?(point, plane)
        # Get plane normal (handle both plane formats)
        normal = if plane.size == 2
                   plane[1].normalize
                 else
                   # [a, b, c, d] format - normal is [a, b, c]
                   ::Geom::Vector3d.new(plane[0], plane[1], plane[2]).normalize
                 end

        (point - point.project_to_plane(plane)) % normal > 0
      end
    end
  end
end
