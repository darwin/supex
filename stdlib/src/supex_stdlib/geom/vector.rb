# frozen_string_literal: true

# Vector utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  module Geom
    # Utilities for working with Geom::Vector3d objects.
    module Vector
      extend self

      # Find an arbitrary unit vector that is not parallel to the given vector.
      #
      # @param vector [Geom::Vector3d]
      # @return [Geom::Vector3d] Z_AXIS or X_AXIS
      #
      # @example
      #   non_parallel = SupexStdlib::Geom::Vector.arbitrary_non_parallel(normal)
      def arbitrary_non_parallel(vector)
        vector.parallel?(Z_AXIS) ? X_AXIS : Z_AXIS
      end

      # Find an arbitrary unit vector that is perpendicular to the given vector.
      #
      # @param vector [Geom::Vector3d]
      # @return [Geom::Vector3d] normalized perpendicular vector
      #
      # @example
      #   perp = SupexStdlib::Geom::Vector.arbitrary_perpendicular(normal)
      def arbitrary_perpendicular(vector)
        (vector * arbitrary_non_parallel(vector)).normalize
      end

      # Transform a normal vector correctly under non-uniform scaling/shearing.
      #
      # Transforming a normal vector as an ordinary vector can give it a faulty
      # direction if the transformation is non-uniformly scaled or sheared.
      # This method ensures the vector stays perpendicular to its original
      # perpendicular plane when a transformation is applied.
      #
      # The correct way to transform a normal is to use the transpose of
      # the inverse of the transformation matrix.
      #
      # @param normal [Geom::Vector3d] normal vector to transform
      # @param transformation [Geom::Transformation] transformation to apply
      # @return [Geom::Vector3d] correctly transformed and normalized normal
      #
      # @example
      #   transformed = SupexStdlib::Geom::Vector.transform_as_normal(normal, tr)
      def transform_as_normal(normal, transformation)
        # Get the 3x3 rotation/scale matrix from the transformation
        # and compute its transpose, then inverse, then apply to normal
        #
        # For a pure rotation, transpose = inverse, so this simplifies.
        # For scaling/shearing, we need the full computation.

        # Extract the 3x3 matrix
        a = transformation.to_a
        m = [
          [a[0], a[1], a[2]],
          [a[4], a[5], a[6]],
          [a[8], a[9], a[10]]
        ]

        # Transpose
        mt = [
          [m[0][0], m[1][0], m[2][0]],
          [m[0][1], m[1][1], m[2][1]],
          [m[0][2], m[1][2], m[2][2]]
        ]

        # Create transformation from transposed matrix (at origin)
        tr_t = ::Geom::Transformation.new([
                                            mt[0][0], mt[0][1], mt[0][2], 0,
                                            mt[1][0], mt[1][1], mt[1][2], 0,
                                            mt[2][0], mt[2][1], mt[2][2], 0,
                                            0, 0, 0, 1
                                          ])

        # Apply inverse of transpose to normal
        normal.transform(tr_t.inverse).normalize
      end
    end
  end
end
