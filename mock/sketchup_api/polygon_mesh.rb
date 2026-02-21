# frozen_string_literal: true

module SketchupMock
  # MockPolygonMesh with 1-based indexing (SketchUp convention).
  # Used by Face#mesh() to return triangulated geometry.
  class MockPolygonMesh
    def initialize
      @points = []   # Array of Geom::Point3d
      @normals = []  # Array of Geom::Vector3d
      @polygons = [] # Array of [idx1, idx2, idx3] (1-based)
    end

    # Add a point, returns 1-based index
    def add_point(point)
      @points << point
      @points.length
    end

    # Add a polygon (1-based vertex indices)
    def add_polygon(*indices)
      @polygons << indices.flatten
    end

    # Set normal for a 1-based index
    def set_normal(index, normal)
      @normals[index - 1] = normal
    end

    # Get point at 1-based index
    def point_at(index)
      @points[index - 1]
    end

    # Get normal at 1-based index
    def normal_at(index)
      @normals[index - 1] || Geom::Vector3d.new(0, 0, 1)
    end

    # Get polygon at 1-based index, returns array of 1-based point indices
    def polygon_at(index)
      @polygons[index - 1]
    end

    def count_points
      @points.length
    end

    def count_polygons
      @polygons.length
    end
  end
end
