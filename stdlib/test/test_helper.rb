# frozen_string_literal: true

require 'minitest/autorun'

# Prevent loading actual SketchUp
$LOADED_FEATURES << 'sketchup.rb'
$LOADED_FEATURES << 'sketchup'

# Minimal SketchUp mock for stdlib testing
module Sketchup
  @platform = RUBY_PLATFORM.include?('darwin') ? :platform_osx : :platform_win
  @temp_dir = Dir.tmpdir
  @version = '24.0'

  class << self
    attr_accessor :platform, :temp_dir, :version
  end

  # Mock Entity classes for Entity module testing
  class Entity
    attr_accessor :attribute_dictionaries

    def get_attribute(dict, key, default = nil)
      return default unless @attribute_dictionaries

      dict_obj = @attribute_dictionaries.find { |d| d.name == dict }
      return default unless dict_obj

      dict_obj[key] || default
    end

    def set_attribute(dict, key, value)
      @attribute_dictionaries ||= []
      dict_obj = @attribute_dictionaries.find { |d| d.name == dict }
      unless dict_obj
        dict_obj = AttributeDictionary.new(dict)
        @attribute_dictionaries << dict_obj
      end
      dict_obj[key] = value
    end
  end

  class AttributeDictionary
    attr_reader :name

    def initialize(name)
      @name = name
      @data = {}
    end

    def [](key)
      @data[key]
    end

    def []=(key, value)
      @data[key] = value
    end

    def each_pair(&)
      @data.each_pair(&)
    end
  end

  class Group < Entity
    attr_accessor :transformation, :definition, :material, :layer, :parent

    def hidden?
      @hidden || false
    end

    attr_writer :hidden

    def erase!
      @erased = true
    end
  end

  class ComponentInstance < Entity
    attr_accessor :transformation, :definition, :material, :layer, :parent

    def hidden?
      @hidden || false
    end

    attr_writer :hidden

    def erase!
      @erased = true
    end
  end

  class ComponentDefinition
    attr_accessor :instances, :name

    def initialize(name = 'Definition')
      @name = name
      @instances = []
      @is_group = false
    end

    def group?
      @is_group
    end

    def group=(val)
      @is_group = val
    end
  end

  class Image < Entity
    attr_accessor :model
  end

  class Camera
    attr_accessor :aspect_ratio, :fov, :height

    def initialize
      @aspect_ratio = 0.0  # 0 means use viewport ratio
      @fov = 35.0          # Default SketchUp FOV
      @fov_is_height = true
      @height = 100.0      # For parallel projection
      @perspective = true
    end

    def fov_is_height?
      @fov_is_height
    end

    attr_writer :fov_is_height, :perspective

    def perspective?
      @perspective
    end
  end

  class View
    attr_accessor :vpwidth, :vpheight, :camera

    def initialize
      @vpwidth = 1920
      @vpheight = 1080
      @camera = Camera.new
    end
  end
end

# Mock UI module for Command testing
module UI
  class Command
    attr_accessor :small_icon, :large_icon, :tooltip, :status_bar_text, :menu_text

    def initialize(title, &block)
      @title = title
      @block = block
    end

    attr_reader :title

    def execute
      @block&.call
    end
  end

  def self.messagebox(message)
    # Mock - do nothing
    message
  end
end

# Continue Sketchup module
module Sketchup
  class Vertex
    attr_accessor :position

    def initialize(position)
      @position = position
    end
  end

  class Edge < Entity
    attr_accessor :start, :end, :faces

    def initialize(start_pos, end_pos)
      @start = Vertex.new(start_pos)
      @end = Vertex.new(end_pos)
      @faces = []
    end

    def length
      @start.position.distance(@end.position)
    end

    def vertices
      [@start, @end]
    end
  end

  class Loop
    attr_accessor :vertices, :edges

    def initialize
      @vertices = []
      @edges = []
    end
  end

  class PolygonMesh
    attr_accessor :polygons, :points

    def initialize
      @polygons = []
      @points = []
    end

    def polygon_points_at(index)
      # Return 3 points for a triangle
      start = (index - 1) * 3
      @points[start, 3] || @points[0, 3]
    end

    def point_at(index)
      @points[index - 1]
    end
  end

  class Color
    attr_accessor :red, :green, :blue, :alpha

    def initialize(red = 0, green = 0, blue = 0, alpha = 255)
      @red = red
      @green = green
      @blue = blue
      @alpha = alpha
    end
  end

  class Face < Entity
    # Point classification constants
    PointUnknown   = 0
    PointInside    = 1
    PointOnVertex  = 2
    PointOnEdge    = 4
    PointOutside   = 8
    PointNotOnPlane = 16

    def initialize
      @outer_loop = Loop.new
      @loops = [@outer_loop]
      @edges = []
      @mesh = PolygonMesh.new
      @area = 1.0
    end

    attr_accessor :outer_loop, :loops, :edges, :mesh, :normal, :area

    def classify_point(_point)
      # Default implementation - returns PointInside
      PointInside
    end
  end
end

# Mock Geom module (SketchUp's built-in geometry)
module Geom
  TOLERANCE = 1e-10

  def self.linear_combination(weight1, point1, weight2, point2)
    Point3d.new(
      weight1 * point1.x + weight2 * point2.x,
      weight1 * point1.y + weight2 * point2.y,
      weight1 * point1.z + weight2 * point2.z
    )
  end

  # Mock Point3d
  class Point3d
    attr_accessor :x, :y, :z

    def initialize(x = 0, y = 0, z = 0)
      if x.is_a?(Array)
        @x = x[0].to_f
        @y = x[1].to_f
        @z = x[2].to_f
      else
        @x = x.to_f
        @y = y.to_f
        @z = z.to_f
      end
    end

    def to_a
      [@x, @y, @z]
    end

    def clone
      Point3d.new(@x, @y, @z)
    end

    def ==(other)
      return false unless other.respond_to?(:x) && other.respond_to?(:y) && other.respond_to?(:z)

      (other.x - @x).abs < TOLERANCE &&
        (other.y - @y).abs < TOLERANCE &&
        (other.z - @z).abs < TOLERANCE
    end

    def -(other)
      if other.is_a?(Point3d)
        Vector3d.new(@x - other.x, @y - other.y, @z - other.z)
      elsif other.is_a?(Vector3d)
        Point3d.new(@x - other.x, @y - other.y, @z - other.z)
      else
        raise ArgumentError, "Cannot subtract #{other.class} from Point3d"
      end
    end

    def +(other)
      Point3d.new(@x + other.x, @y + other.y, @z + other.z)
    end

    def offset(vector, distance = nil)
      if distance
        # offset(vector, distance) form - scale vector to distance
        scaled = vector.normalize.transform(distance)
        Point3d.new(@x + scaled.x, @y + scaled.y, @z + scaled.z)
      else
        Point3d.new(@x + vector.x, @y + vector.y, @z + vector.z)
      end
    end

    def vector_to(other)
      Vector3d.new(other.x - @x, other.y - @y, other.z - @z)
    end

    def distance(other)
      Math.sqrt((@x - other.x)**2 + (@y - other.y)**2 + (@z - other.z)**2)
    end

    def on_line?(line)
      point, direction = line
      direction = point.vector_to(direction) unless direction.is_a?(Vector3d)
      return true if self == point

      to_point = point.vector_to(self)
      return false unless to_point.valid?

      to_point.parallel?(direction)
    end

    def on_plane?(plane)
      if plane.size == 2
        plane_point, normal = plane
        normal = Vector3d.new(normal) unless normal.is_a?(Vector3d)
      else
        a, b, c, d = plane
        normal = Vector3d.new(a, b, c).normalize
        # Find a point on the plane
        len_sq = a * a + b * b + c * c
        plane_point = Point3d.new(-a * d / len_sq, -b * d / len_sq, -c * d / len_sq)
      end
      # Point is on plane if vector from plane_point to self is perpendicular to normal
      to_self = plane_point.vector_to(self)
      return true unless to_self.valid?

      (to_self % normal).abs < TOLERANCE
    end

    def project_to_plane(plane)
      if plane.size == 2
        plane_point, normal = plane
      else
        a, b, c, d = plane
        normal = Vector3d.new(a, b, c).normalize
        plane_point = Point3d.new(a * -d / (a * a + b * b + c * c),
                                  b * -d / (a * a + b * b + c * c),
                                  c * -d / (a * a + b * b + c * c))
      end
      dist = (self - plane_point) % normal
      offset(normal.reverse.transform(dist))
    end

    def transform(tr)
      a = tr.to_a
      new_x = a[0] * @x + a[4] * @y + a[8] * @z + a[12]
      new_y = a[1] * @x + a[5] * @y + a[9] * @z + a[13]
      new_z = a[2] * @x + a[6] * @y + a[10] * @z + a[14]
      Point3d.new(new_x, new_y, new_z)
    end

    def transform!(tr)
      a = tr.to_a
      new_x = a[0] * @x + a[4] * @y + a[8] * @z + a[12]
      new_y = a[1] * @x + a[5] * @y + a[9] * @z + a[13]
      new_z = a[2] * @x + a[6] * @y + a[10] * @z + a[14]
      @x = new_x
      @y = new_y
      @z = new_z
      self
    end

    def inspect
      "Point3d(#{@x}, #{@y}, #{@z})"
    end
  end

  # Mock Vector3d
  class Vector3d
    attr_accessor :x, :y, :z

    def initialize(x = 0, y = 0, z = 0)
      if x.is_a?(Array)
        @x = x[0].to_f
        @y = x[1].to_f
        @z = x[2].to_f
      else
        @x = x.to_f
        @y = y.to_f
        @z = z.to_f
      end
    end

    def to_a
      [@x, @y, @z]
    end

    def clone
      Vector3d.new(@x, @y, @z)
    end

    def length
      Math.sqrt(@x * @x + @y * @y + @z * @z)
    end

    def valid?
      length > TOLERANCE
    end

    def normalize
      len = length
      return Vector3d.new(0, 0, 0) if len < TOLERANCE

      Vector3d.new(@x / len, @y / len, @z / len)
    end

    def normalize!
      len = length
      return self if len < TOLERANCE

      @x /= len
      @y /= len
      @z /= len
      self
    end

    def reverse
      Vector3d.new(-@x, -@y, -@z)
    end

    def ==(other)
      return false unless other.respond_to?(:x) && other.respond_to?(:y) && other.respond_to?(:z)

      (other.x - @x).abs < TOLERANCE &&
        (other.y - @y).abs < TOLERANCE &&
        (other.z - @z).abs < TOLERANCE
    end

    def +(other)
      Vector3d.new(@x + other.x, @y + other.y, @z + other.z)
    end

    def -(other)
      Vector3d.new(@x - other.x, @y - other.y, @z - other.z)
    end

    # Cross product
    def *(other)
      if other.is_a?(Numeric)
        Vector3d.new(@x * other, @y * other, @z * other)
      else
        Vector3d.new(
          @y * other.z - @z * other.y,
          @z * other.x - @x * other.z,
          @x * other.y - @y * other.x
        )
      end
    end

    # Dot product
    def %(other)
      @x * other.x + @y * other.y + @z * other.z
    end

    def dot(other)
      self % other
    end

    def cross(other)
      self * other
    end

    def parallel?(other)
      cross = self * other
      cross.length < TOLERANCE
    end

    def samedirection?(other)
      return false unless parallel?(other)

      dot(other) > 0
    end

    def angle_between(other)
      dot_product = self % other
      len_product = length * other.length
      return 0.0 if len_product < TOLERANCE

      cos_angle = [[-1.0, dot_product / len_product].max, 1.0].min
      Math.acos(cos_angle)
    end

    def transform(tr)
      if tr.is_a?(Numeric)
        # Scale
        Vector3d.new(@x * tr, @y * tr, @z * tr)
      else
        a = tr.to_a
        new_x = a[0] * @x + a[4] * @y + a[8] * @z
        new_y = a[1] * @x + a[5] * @y + a[9] * @z
        new_z = a[2] * @x + a[6] * @y + a[10] * @z
        Vector3d.new(new_x, new_y, new_z)
      end
    end

    def inspect
      "Vector3d(#{@x}, #{@y}, #{@z})"
    end
  end

  # Mock Transformation
  class Transformation
    def initialize(arg = nil)
      @matrix = if arg.nil?
                  # Identity matrix
                  [
                    1, 0, 0, 0,
                    0, 1, 0, 0,
                    0, 0, 1, 0,
                    0, 0, 0, 1
                  ]
                elsif arg.is_a?(Array) && arg.size == 16
                  arg.map(&:to_f)
                elsif arg.is_a?(Point3d)
                  # Translation
                  [
                    1, 0, 0, 0,
                    0, 1, 0, 0,
                    0, 0, 1, 0,
                    arg.x, arg.y, arg.z, 1
                  ]
                else
                  [
                    1, 0, 0, 0,
                    0, 1, 0, 0,
                    0, 0, 1, 0,
                    0, 0, 0, 1
                  ]
                end
    end

    def to_a
      @matrix.dup
    end

    def inverse
      # Simplified inverse for testing (works for common cases)
      a = @matrix
      det = determinant
      return Transformation.new if det.abs < TOLERANCE

      # Compute adjugate matrix and divide by determinant
      inv = Array.new(16, 0.0)

      inv[0] =
        (a[5] * (a[10] * a[15] - a[11] * a[14]) - a[9] * (a[6] * a[15] - a[7] * a[14]) + a[13] * (a[6] * a[11] - a[7] * a[10])) / det
      inv[4] =
        -(a[4] * (a[10] * a[15] - a[11] * a[14]) - a[8] * (a[6] * a[15] - a[7] * a[14]) + a[12] * (a[6] * a[11] - a[7] * a[10])) / det
      inv[8] =
        (a[4] * (a[9] * a[15] - a[11] * a[13]) - a[8] * (a[5] * a[15] - a[7] * a[13]) + a[12] * (a[5] * a[11] - a[7] * a[9])) / det
      inv[12] =
        -(a[4] * (a[9] * a[14] - a[10] * a[13]) - a[8] * (a[5] * a[14] - a[6] * a[13]) + a[12] * (a[5] * a[10] - a[6] * a[9])) / det

      inv[1] =
        -(a[1] * (a[10] * a[15] - a[11] * a[14]) - a[9] * (a[2] * a[15] - a[3] * a[14]) + a[13] * (a[2] * a[11] - a[3] * a[10])) / det
      inv[5] =
        (a[0] * (a[10] * a[15] - a[11] * a[14]) - a[8] * (a[2] * a[15] - a[3] * a[14]) + a[12] * (a[2] * a[11] - a[3] * a[10])) / det
      inv[9] =
        -(a[0] * (a[9] * a[15] - a[11] * a[13]) - a[8] * (a[1] * a[15] - a[3] * a[13]) + a[12] * (a[1] * a[11] - a[3] * a[9])) / det
      inv[13] =
        (a[0] * (a[9] * a[14] - a[10] * a[13]) - a[8] * (a[1] * a[14] - a[2] * a[13]) + a[12] * (a[1] * a[10] - a[2] * a[9])) / det

      inv[2] =
        (a[1] * (a[6] * a[15] - a[7] * a[14]) - a[5] * (a[2] * a[15] - a[3] * a[14]) + a[13] * (a[2] * a[7] - a[3] * a[6])) / det
      inv[6] =
        -(a[0] * (a[6] * a[15] - a[7] * a[14]) - a[4] * (a[2] * a[15] - a[3] * a[14]) + a[12] * (a[2] * a[7] - a[3] * a[6])) / det
      inv[10] =
        (a[0] * (a[5] * a[15] - a[7] * a[13]) - a[4] * (a[1] * a[15] - a[3] * a[13]) + a[12] * (a[1] * a[7] - a[3] * a[5])) / det
      inv[14] =
        -(a[0] * (a[5] * a[14] - a[6] * a[13]) - a[4] * (a[1] * a[14] - a[2] * a[13]) + a[12] * (a[1] * a[6] - a[2] * a[5])) / det

      inv[3] =
        -(a[1] * (a[6] * a[11] - a[7] * a[10]) - a[5] * (a[2] * a[11] - a[3] * a[10]) + a[9] * (a[2] * a[7] - a[3] * a[6])) / det
      inv[7] =
        (a[0] * (a[6] * a[11] - a[7] * a[10]) - a[4] * (a[2] * a[11] - a[3] * a[10]) + a[8] * (a[2] * a[7] - a[3] * a[6])) / det
      inv[11] =
        -(a[0] * (a[5] * a[11] - a[7] * a[9]) - a[4] * (a[1] * a[11] - a[3] * a[9]) + a[8] * (a[1] * a[7] - a[3] * a[5])) / det
      inv[15] =
        (a[0] * (a[5] * a[10] - a[6] * a[9]) - a[4] * (a[1] * a[10] - a[2] * a[9]) + a[8] * (a[1] * a[6] - a[2] * a[5])) / det

      Transformation.new(inv)
    end

    def determinant
      a = @matrix
      a[0] * (a[5] * (a[10] * a[15] - a[11] * a[14]) - a[9] * (a[6] * a[15] - a[7] * a[14]) + a[13] * (a[6] * a[11] - a[7] * a[10])) -
        a[4] * (a[1] * (a[10] * a[15] - a[11] * a[14]) - a[9] * (a[2] * a[15] - a[3] * a[14]) + a[13] * (a[2] * a[11] - a[3] * a[10])) +
        a[8] * (a[1] * (a[6] * a[15] - a[7] * a[14]) - a[5] * (a[2] * a[15] - a[3] * a[14]) + a[13] * (a[2] * a[7] - a[3] * a[6])) -
        a[12] * (a[1] * (a[6] * a[11] - a[7] * a[10]) - a[5] * (a[2] * a[11] - a[3] * a[10]) + a[9] * (a[2] * a[7] - a[3] * a[6]))
    end

    def *(other)
      if other.is_a?(Transformation)
        a = @matrix
        b = other.to_a
        result = Array.new(16, 0.0)
        4.times do |row|
          4.times do |col|
            4.times do |k|
              result[col * 4 + row] += a[k * 4 + row] * b[col * 4 + k]
            end
          end
        end
        Transformation.new(result)
      else
        raise ArgumentError, "Cannot multiply Transformation by #{other.class}"
      end
    end

    def origin
      Point3d.new(@matrix[12], @matrix[13], @matrix[14])
    end

    def self.rotation(point, axis, angle)
      # Rotation around arbitrary axis using Rodrigues' rotation formula
      c = Math.cos(angle)
      s = Math.sin(angle)
      t = 1 - c

      # Normalize axis
      len = Math.sqrt(axis.x**2 + axis.y**2 + axis.z**2)
      x = axis.x / len
      y = axis.y / len
      z = axis.z / len

      # Rotation matrix
      r00 = t * x * x + c
      r01 = t * x * y - s * z
      r02 = t * x * z + s * y
      r10 = t * x * y + s * z
      r11 = t * y * y + c
      r12 = t * y * z - s * x
      r20 = t * x * z - s * y
      r21 = t * y * z + s * x
      r22 = t * z * z + c

      # Build transformation with rotation at point
      # T(point) * R * T(-point)
      px = point.x
      py = point.y
      pz = point.z
      tx = px - (r00 * px + r01 * py + r02 * pz)
      ty = py - (r10 * px + r11 * py + r12 * pz)
      tz = pz - (r20 * px + r21 * py + r22 * pz)

      new([
            r00, r10, r20, 0,
            r01, r11, r21, 0,
            r02, r12, r22, 0,
            tx, ty, tz, 1
          ])
    end

    def self.scaling(point, xscale, yscale = nil, zscale = nil)
      yscale ||= xscale
      zscale ||= xscale

      # T(point) * S * T(-point)
      px = point.x
      py = point.y
      pz = point.z
      tx = px - xscale * px
      ty = py - yscale * py
      tz = pz - zscale * pz

      new([
            xscale, 0, 0, 0,
            0, yscale, 0, 0,
            0, 0, zscale, 0,
            tx, ty, tz, 1
          ])
    end
  end
end

# Global constants (like SketchUp provides)
ORIGIN = Geom::Point3d.new(0, 0, 0)
X_AXIS = Geom::Vector3d.new(1, 0, 0)
Y_AXIS = Geom::Vector3d.new(0, 1, 0)
Z_AXIS = Geom::Vector3d.new(0, 0, 1)
IDENTITY = Geom::Transformation.new

# Load stdlib
require_relative '../src/supex_stdlib'
