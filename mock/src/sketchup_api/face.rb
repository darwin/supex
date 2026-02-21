# frozen_string_literal: true

module Sketchup
  class Face < Entity
    attr_accessor :area, :normal, :bounds

    def initialize(area: 100.0)
      super()
      @area = area
      @normal = Geom::Vector3d.new(0, 0, 1)
      @bounds = Geom::BoundingBox.new
      @mesh_data = nil
    end

    # Set mesh data for mock (used by test control)
    def set_mesh_data(mesh)
      @mesh_data = mesh
    end

    # SketchUp Face#mesh returns a PolygonMesh
    # flags parameter is ignored in mock
    def mesh(_flags = 0)
      @mesh_data || default_mesh
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end

    private

    def default_mesh
      pm = SketchupMock::MockPolygonMesh.new
      pm.add_point(Geom::Point3d.new(0, 0, 0))
      pm.add_point(Geom::Point3d.new(1, 0, 0))
      pm.add_point(Geom::Point3d.new(1, 1, 0))
      pm.add_polygon(1, 2, 3)
      pm
    end
  end

  class Edge < Entity
    attr_accessor :length, :bounds

    def initialize(length: 10.0)
      super()
      @length = length
      @bounds = Geom::BoundingBox.new
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end
  end

  class Group < Entity
    attr_accessor :name, :bounds

    def initialize(name: '')
      super()
      @name = name
      @bounds = Geom::BoundingBox.new
      @parent_ref = nil
    end

    def parent
      @parent_ref
    end

    def parent=(p)
      @parent_ref = p
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end
  end

  # Sketchup::Camera for batch_screenshot compatibility
  class Camera < SketchupMock::MockCamera
  end

  # Sketchup::InstancePath for isolation tests
  class InstancePath
    attr_reader :path

    def initialize(path)
      @path = path
    end

    def root
      @path.first
    end

    def leaf
      @path.last
    end
  end
end
