# frozen_string_literal: true

# Geom::Point3d, Geom::Vector3d, Geom::BoundingBox
# Matching SketchUp API geometry primitives.
module Geom
  class Point3d
    attr_accessor :x, :y, :z

    def initialize(*args)
      if args.length == 3
        @x = args[0].to_f
        @y = args[1].to_f
        @z = args[2].to_f
      elsif args.length == 1 && args[0].is_a?(Array)
        @x = args[0][0].to_f
        @y = args[0][1].to_f
        @z = args[0][2].to_f
      else
        @x = 0.0
        @y = 0.0
        @z = 0.0
      end
    end

    def to_a
      [@x, @y, @z]
    end

    def vector_to(other)
      Vector3d.new(other.x - @x, other.y - @y, other.z - @z)
    end

    def offset(vector, distance = nil)
      if distance
        Point3d.new(@x + (vector.x * distance), @y + (vector.y * distance), @z + (vector.z * distance))
      else
        Point3d.new(@x + vector.x, @y + vector.y, @z + vector.z)
      end
    end

    def distance(other)
      Math.sqrt(((@x - other.x)**2) + ((@y - other.y)**2) + ((@z - other.z)**2))
    end

    def ==(other)
      other.is_a?(Point3d) && @x == other.x && @y == other.y && @z == other.z
    end

    def inspect
      "Point3d(#{@x}, #{@y}, #{@z})"
    end
  end

  class Vector3d
    attr_accessor :x, :y, :z

    def initialize(*args)
      if args.length == 3
        @x = args[0].to_f
        @y = args[1].to_f
        @z = args[2].to_f
      elsif args.length == 1 && args[0].is_a?(Array)
        @x = args[0][0].to_f
        @y = args[0][1].to_f
        @z = args[0][2].to_f
      else
        @x = 0.0
        @y = 0.0
        @z = 0.0
      end
    end

    def to_a
      [@x, @y, @z]
    end

    def length
      Math.sqrt((@x**2) + (@y**2) + (@z**2))
    end

    def normalize!
      len = length
      return self if len < 0.0001

      @x /= len
      @y /= len
      @z /= len
      self
    end

    def normalize
      dup.normalize!
    end

    def reverse
      Vector3d.new(-@x, -@y, -@z)
    end

    def parallel?(other)
      cx = (@y * other.z) - (@z * other.y)
      cy = (@z * other.x) - (@x * other.z)
      cz = (@x * other.y) - (@y * other.x)
      cx.abs < 0.0001 && cy.abs < 0.0001 && cz.abs < 0.0001
    end

    def ==(other)
      other.is_a?(Vector3d) && @x == other.x && @y == other.y && @z == other.z
    end

    def inspect
      "Vector3d(#{@x}, #{@y}, #{@z})"
    end
  end

  class BoundingBox
    attr_reader :min, :max

    def initialize
      @min = Point3d.new(1e30, 1e30, 1e30)
      @max = Point3d.new(-1e30, -1e30, -1e30)
      @empty = true
    end

    def add(point)
      @empty = false
      @min.x = [@min.x, point.x].min
      @min.y = [@min.y, point.y].min
      @min.z = [@min.z, point.z].min
      @max.x = [@max.x, point.x].max
      @max.y = [@max.y, point.y].max
      @max.z = [@max.z, point.z].max
    end

    def center
      Point3d.new(
        (@min.x + @max.x) / 2.0,
        (@min.y + @max.y) / 2.0,
        (@min.z + @max.z) / 2.0
      )
    end

    def empty?
      @empty
    end

    def diagonal
      return 0.0 if @empty

      Math.sqrt(
        ((@max.x - @min.x)**2) +
        ((@max.y - @min.y)**2) +
        ((@max.z - @min.z)**2)
      )
    end

    def width
      @empty ? 0.0 : @max.x - @min.x
    end

    def height
      @empty ? 0.0 : @max.z - @min.z
    end

    def depth
      @empty ? 0.0 : @max.y - @min.y
    end
  end
end
