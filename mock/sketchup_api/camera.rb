# frozen_string_literal: true

module SketchupMock
  class MockCamera
    attr_accessor :eye, :target, :up, :fov, :aspect_ratio, :height

    def initialize(eye = nil, target = nil, up = nil, perspective = true, fov = 45.0)
      @eye = eye || Geom::Point3d.new(0, 0, 100)
      @target = target || Geom::Point3d.new(0, 0, 0)
      @up = up || Geom::Vector3d.new(0, 1, 0)
      @fov = fov
      @aspect_ratio = 1.777
      @perspective = perspective
      @height = 100.0
    end

    def perspective?
      @perspective
    end

    attr_writer :perspective

    def set(eye, target, up)
      @eye = eye
      @target = target
      @up = up
    end

    def direction
      @eye.vector_to(@target).normalize
    end
  end

  class MockView
    attr_accessor :camera

    def initialize
      @camera = MockCamera.new
    end

    def write_image(options)
      FileUtils.touch(options[:filename]) if options[:filename]
      true
    end

    def zoom_extents
      true
    end

    def zoom(_entities_or_factor)
      true
    end

    def invalidate
      true
    end
  end

  class MockRenderingOptions
    def initialize
      @options = {
        'InactiveHidden' => false,
        'DrawHidden' => false
      }
    end

    def [](key)
      @options[key]
    end

    def []=(key, value)
      @options[key] = value
    end
  end
end
