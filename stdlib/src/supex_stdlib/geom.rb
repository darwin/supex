# frozen_string_literal: true

# Geometry utilities adapted from SketchUp community libraries (MIT License):
# - mid_point, offset_points: tt-lib by Thomas Thomassen
#   https://github.com/thomthom/tt-lib
# - polygon_area, polygon_normal, remove_duplicates, angle_in_plane:
#   sketchup-community-lib https://github.com/Eneroth3/sketchup-community-lib

require_relative 'geom/point'
require_relative 'geom/vector'
require_relative 'geom/line'
require_relative 'geom/plane'
require_relative 'geom/transformation'
require_relative 'geom/bounding_box'

module SupexStdlib
  # Geometry utilities extending SketchUp's native Geom module.
  #
  # Provides helper methods for working with points, vectors, planes,
  # and transformations.
  module Geom
    extend self

    # Calculate midpoint between two points or along an edge.
    #
    # @overload mid_point(edge)
    #   @param edge [Sketchup::Edge] edge to find midpoint of
    #   @return [Geom::Point3d]
    #
    # @overload mid_point(point1, point2)
    #   @param point1 [Geom::Point3d] first point
    #   @param point2 [Geom::Point3d] second point
    #   @return [Geom::Point3d]
    #
    # @example
    #   mid = SupexStdlib::Geom.mid_point(pt1, pt2)
    #   mid = SupexStdlib::Geom.mid_point(edge)
    def mid_point(*args)
      case args.size
      when 1 # Edge
        points = args.first.vertices.map(&:position)
      when 2 # Points
        points = args
      else
        raise ArgumentError, "wrong number of arguments (#{args.size} for 1..2)"
      end
      ::Geom.linear_combination(0.5, points.first, 0.5, points.last)
    end

    # Offset an array of points by a vector.
    #
    # @param points [Array<Geom::Point3d>] points to offset
    # @param vector [Geom::Vector3d] offset vector
    # @return [Array<Geom::Point3d>] new array of offset points
    #
    # @example
    #   offset_pts = SupexStdlib::Geom.offset_points(points, Z_AXIS * 10)
    def offset_points(points, vector)
      points.map { |point| point.offset(vector) }
    end

    # Compute area of a polygon defined by an array of points.
    #
    # Uses Newell's method to compute the polygon area.
    #
    # @param points [Array<Geom::Point3d>] polygon vertices
    # @return [Float] polygon area
    #
    # @example
    #   area = SupexStdlib::Geom.polygon_area(face.outer_loop.vertices.map(&:position))
    def polygon_area(points)
      origin = points.first
      normal = polygon_normal(points)

      area = 0
      points.each_with_index do |pt0, i|
        pt1 = points[i + 1] || points.first
        triangle_area = ((pt1 - pt0) * (origin - pt0)).length / 2
        if (pt1 - pt0) * (origin - pt0) % normal > 0
          area += triangle_area
        else
          area -= triangle_area
        end
      end

      area
    end

    # Find normal vector from polygon vertices using Newell's method.
    #
    # @param points [Array<Geom::Point3d>] polygon vertices
    # @return [Geom::Vector3d] normalized normal vector
    #
    # @example
    #   normal = SupexStdlib::Geom.polygon_normal(points)
    def polygon_normal(points)
      normal = ::Geom::Vector3d.new(0, 0, 0)
      points.each_with_index do |pt0, i|
        pt1 = points[i + 1] || points.first
        normal.x = normal.x + (pt0.y - pt1.y) * (pt0.z + pt1.z)
        normal.y = normal.y + (pt0.z - pt1.z) * (pt0.x + pt1.x)
        normal.z = normal.z + (pt0.x - pt1.x) * (pt0.y + pt1.y)
      end

      normal.normalize
    end

    # Remove duplicate points or vectors from array using SketchUp's precision.
    #
    # Ruby's Array#uniq doesn't remove duplicate points as they are regarded
    # as separate objects based on #eql? and #hash. This method uses SketchUp's
    # == operator which has tolerance for floating point comparison.
    #
    # @param array [Array] array of points or vectors
    # @return [Array] array with duplicates removed
    def remove_duplicates(array)
      array.reduce([]) { |a, c1| a.any? { |c2| c2 == c1 } ? a : a << c1 }
    end

    # Calculate angle from subtrahend to minuend vector, projected to a plane.
    #
    # Returns angle in radians from 0.0 to 2*PI. Angle is measured
    # counter-clockwise as seen from the direction normal points towards.
    #
    # @param minuend [Geom::Vector3d]
    # @param subtrahend [Geom::Vector3d]
    # @param normal [Geom::Vector3d] plane normal (default: Z_AXIS)
    # @return [Float] angle in radians (0 to 2*PI)
    #
    # @example
    #   angle = SupexStdlib::Geom.angle_in_plane(vec1, vec2, Z_AXIS)
    def angle_in_plane(minuend, subtrahend, normal = Z_AXIS)
      # Project vectors to plane by double cross product
      minuend = normal * minuend * normal
      subtrahend = normal * subtrahend * normal

      # Determine if we need to go the "long way" around
      if (minuend * subtrahend) % normal > 0
        Math::PI * 2 - minuend.angle_between(subtrahend)
      else
        minuend.angle_between(subtrahend)
      end
    end
  end
end
