# frozen_string_literal: true

# Edge utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  # Utilities for working with Sketchup::Edge entities.
  module Edge
    extend self

    # Get the midpoint position for an edge.
    #
    # @param edge [Sketchup::Edge]
    # @return [Geom::Point3d]
    #
    # @example
    #   mid = SupexStdlib::Edge.midpoint(edge)
    def midpoint(edge)
      ::Geom.linear_combination(
        0.5,
        edge.start.position,
        0.5,
        edge.end.position
      )
    end

    # Get the length of an edge.
    #
    # @param edge [Sketchup::Edge]
    # @return [Float] length in model units
    def length(edge)
      edge.length
    end

    # Get the direction vector of an edge.
    #
    # @param edge [Sketchup::Edge]
    # @return [Geom::Vector3d] normalized direction vector
    def direction(edge)
      edge.start.position.vector_to(edge.end.position).normalize
    end

    # Test if two edges are parallel.
    #
    # @param edge1 [Sketchup::Edge]
    # @param edge2 [Sketchup::Edge]
    # @return [Boolean]
    def parallel?(edge1, edge2)
      direction(edge1).parallel?(direction(edge2))
    end

    # Get the line representation of an edge.
    #
    # @param edge [Sketchup::Edge]
    # @return [Array(Geom::Point3d, Geom::Vector3d)]
    def to_line(edge)
      [edge.start.position, direction(edge)]
    end
  end
end
