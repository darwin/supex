# frozen_string_literal: true

# Geom::Transformation mock.
# Supports construction from Point3d, from 16-element Array, and default identity.
module Geom
  class Transformation
    attr_reader :origin

    def initialize(arg = nil)
      if arg.is_a?(Point3d)
        @origin = arg
        @matrix = identity_matrix
        @matrix[12] = arg.x
        @matrix[13] = arg.y
        @matrix[14] = arg.z
      elsif arg.is_a?(Array) && arg.length == 16
        @matrix = arg.map(&:to_f)
        @origin = Point3d.new(@matrix[12], @matrix[13], @matrix[14])
      else
        @origin = Point3d.new(0, 0, 0)
        @matrix = identity_matrix
      end
    end

    def to_a
      @matrix.dup
    end

    def inspect
      "Transformation(origin: #{@origin.inspect})"
    end

    private

    def identity_matrix
      [1.0, 0.0, 0.0, 0.0,
       0.0, 1.0, 0.0, 0.0,
       0.0, 0.0, 1.0, 0.0,
       0.0, 0.0, 0.0, 1.0]
    end
  end
end
