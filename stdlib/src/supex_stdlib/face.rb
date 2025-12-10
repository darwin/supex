# frozen_string_literal: true

# Face utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  # Utilities for working with Sketchup::Face entities.
  module Face
    extend self

    # Find an arbitrary point within a face.
    #
    # Uses the face's mesh triangulation to find a point guaranteed
    # to be inside the face boundary.
    #
    # @param face [Sketchup::Face]
    # @return [Geom::Point3d, nil] nil for zero-area faces
    #
    # @example
    #   interior = SupexStdlib::Face.arbitrary_interior_point(face)
    def arbitrary_interior_point(face)
      return nil if face.area.zero?

      # In rare situations polygon_points_at returns collinear points,
      # which would lead to a point on the boundary. Loop until we find
      # non-collinear points.
      index = 1
      points = nil
      loop do
        points = face.mesh.polygon_points_at(index)
        index += 1
        break unless points[0].on_line?([points[1], points[2]])
      end

      # Return centroid of the triangle
      ::Geom.linear_combination(
        0.5,
        ::Geom.linear_combination(0.5, points[0], 0.5, points[1]),
        0.5,
        points[2]
      )
    end

    # Test if a point is within a face.
    #
    # @param face [Sketchup::Face]
    # @param point [Geom::Point3d]
    # @param include_boundary [Boolean] whether points on edges/vertices count
    # @return [Boolean]
    #
    # @example
    #   SupexStdlib::Face.includes_point?(face, point)
    def includes_point?(face, point, include_boundary = true)
      pc = face.classify_point(point)
      return include_boundary if [Sketchup::Face::PointOnEdge, Sketchup::Face::PointOnVertex].include?(pc)

      pc == Sketchup::Face::PointInside
    end

    # Get all interior loops (holes) of a face.
    #
    # Returns empty array if face has no holes.
    #
    # @param face [Sketchup::Face]
    # @return [Array<Sketchup::Loop>]
    #
    # @example
    #   holes = SupexStdlib::Face.inner_loops(face)
    def inner_loops(face)
      face.loops - [face.outer_loop]
    end

    # Get the triangles making up a face.
    #
    # Returns an array of triangles, each triangle being an array of 3 points.
    #
    # @param face [Sketchup::Face]
    # @param transformation [Geom::Transformation] transformation to apply
    # @return [Array<Array<Geom::Point3d>>] array of triangles
    #
    # @example
    #   triangles = SupexStdlib::Face.triangulate(face)
    def triangulate(face, transformation = IDENTITY)
      mesh = face.mesh
      indices = mesh.polygons.flatten.map(&:abs)
      points = indices.map { |i| mesh.point_at(i) }
      points.each { |pt| pt.transform!(transformation) }

      points.each_slice(3).to_a
    end

    # Find the exterior face that a face forms a hole within.
    #
    # Returns nil if the face is not inside another face.
    #
    # @param face [Sketchup::Face]
    # @return [Sketchup::Face, nil]
    #
    # @example
    #   outer = SupexStdlib::Face.wrapping_face(inner_face)
    def wrapping_face(face)
      edge_faces = face.edges.map(&:faces)
      return nil if edge_faces.empty?

      common_faces = edge_faces.inject(:&)
      return nil if common_faces.nil?

      (common_faces - [face]).first
    end
  end
end
