# frozen_string_literal: true

# Transformation utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  module Geom
    # Utilities for working with Geom::Transformation objects.
    #
    # Provides inspection, creation, and manipulation methods that extend
    # SketchUp's native Transformation class functionality.
    module Transformation
      extend self

      # Create transformation from origin point and axes vectors.
      #
      # Unlike native Geom::Transformation.axes, this method does not make
      # the axes orthogonal or normalize them, allowing for scaled and
      # sheared transformations.
      #
      # @param origin [Geom::Point3d] origin point
      # @param xaxis [Geom::Vector3d] X axis vector (with scale)
      # @param yaxis [Geom::Vector3d] Y axis vector (with scale)
      # @param zaxis [Geom::Vector3d] Z axis vector (with scale)
      # @return [Geom::Transformation]
      # @raise [ArgumentError] if any axes are parallel or zero length
      #
      # @example
      #   tr = SupexStdlib::Geom::Transformation.from_axes(ORIGIN, X_AXIS, Y_AXIS, Z_AXIS)
      def from_axes(origin = ORIGIN, xaxis = X_AXIS, yaxis = Y_AXIS, zaxis = Z_AXIS)
        raise ArgumentError, 'Axes must not be zero length.' unless [xaxis, yaxis, zaxis].all?(&:valid?)
        if xaxis.parallel?(yaxis) || yaxis.parallel?(zaxis) || zaxis.parallel?(xaxis)
          raise ArgumentError, 'Axes must not be parallel.'
        end

        ::Geom::Transformation.new([
                                     xaxis.x, xaxis.y, xaxis.z, 0,
                                     yaxis.x, yaxis.y, yaxis.z, 0,
                                     zaxis.x, zaxis.y, zaxis.z, 0,
                                     origin.x, origin.y, origin.z, 1
                                   ])
      end

      # Create transformation from origin point and Euler angles.
      #
      # Rotations are applied in ZYX order (extrinsic).
      #
      # @param origin [Geom::Point3d] origin point
      # @param x_angle [Float] rotation around X axis in radians
      # @param y_angle [Float] rotation around Y axis in radians
      # @param z_angle [Float] rotation around Z axis in radians
      # @return [Geom::Transformation]
      #
      # @example
      #   tr = SupexStdlib::Geom::Transformation.from_euler_angles(ORIGIN, 0.5, 0.3, 0.1)
      def from_euler_angles(origin = ORIGIN, x_angle = 0, y_angle = 0, z_angle = 0)
        ::Geom::Transformation.new(origin) *
          ::Geom::Transformation.rotation(ORIGIN, Z_AXIS, z_angle) *
          ::Geom::Transformation.rotation(ORIGIN, Y_AXIS, y_angle) *
          ::Geom::Transformation.rotation(ORIGIN, X_AXIS, x_angle)
      end

      # Calculate determinant of the 3x3 rotation/scale matrix.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      #
      # @example
      #   det = SupexStdlib::Geom::Transformation.determinant(tr)
      def determinant(transformation)
        xaxis(transformation) % (yaxis(transformation) * zaxis(transformation))
      end

      # Calculate extrinsic XYZ Euler angles for transformation.
      #
      # Scaling, shearing and translation are ignored.
      # Rotations are applied in ZYX order.
      #
      # @param transformation [Geom::Transformation]
      # @return [Array(Float, Float, Float)] [x, y, z] angles in radians
      #
      # @example
      #   angles = SupexStdlib::Geom::Transformation.euler_angles(tr)
      def euler_angles(transformation)
        a = remove_scaling(remove_shearing(transformation, false)).to_a

        x = Math.atan2(a[6], a[10])
        c2 = Math.sqrt(a[0]**2 + a[1]**2)
        y = Math.atan2(-a[2], c2)
        s = Math.sin(x)
        c1 = Math.cos(x)
        z = Math.atan2(s * a[8] - c1 * a[4], c1 * a[5] - s * a[9])

        [x, y, z]
      end

      # Extract the shearing component of a transformation.
      #
      # @param transformation [Geom::Transformation]
      # @return [Geom::Transformation] transformation representing only shear
      #
      # @example
      #   shear = SupexStdlib::Geom::Transformation.extract_shearing(tr)
      def extract_shearing(transformation)
        remove_shearing(transformation, true).inverse * transformation
      end

      # Test if transformation is flipped (mirrored).
      #
      # @param transformation [Geom::Transformation]
      # @return [Boolean]
      #
      # @example
      #   SupexStdlib::Geom::Transformation.flipped?(tr)
      def flipped?(transformation)
        determinant(transformation) < 0
      end

      # Test if transformation is the identity transformation.
      #
      # @param transformation [Geom::Transformation]
      # @return [Boolean]
      #
      # @example
      #   SupexStdlib::Geom::Transformation.identity?(tr)
      def identity?(transformation)
        same?(transformation, IDENTITY)
      end

      # Return new transformation with scaling removed.
      #
      # All axes of the new transformation have length 1.
      #
      # @param transformation [Geom::Transformation]
      # @param allow_flip [Boolean] if false and flipped, X axis is reversed
      # @return [Geom::Transformation]
      #
      # @example
      #   unscaled = SupexStdlib::Geom::Transformation.remove_scaling(tr)
      def remove_scaling(transformation, allow_flip = false)
        x_axis = xaxis(transformation).normalize
        x_axis = x_axis.reverse if flipped?(transformation) && !allow_flip
        from_axes(
          transformation.origin,
          x_axis,
          yaxis(transformation).normalize,
          zaxis(transformation).normalize
        )
      end

      # Return new transformation with shearing removed (made orthogonal).
      #
      # X axis is kept as the reference for rotation.
      #
      # @param transformation [Geom::Transformation]
      # @param preserve_determinant [Boolean] if true, preserves volume; if false, preserves axis lengths
      # @return [Geom::Transformation]
      #
      # @example
      #   orthogonal = SupexStdlib::Geom::Transformation.remove_shearing(tr)
      def remove_shearing(transformation, preserve_determinant = false)
        x = xaxis(transformation)
        y = yaxis(transformation)
        z = zaxis(transformation)

        x_norm = x.normalize
        new_yaxis = x_norm * y * x_norm
        y_norm = new_yaxis.normalize
        new_zaxis = y_norm * (x_norm * z * x_norm) * y_norm

        unless preserve_determinant
          new_yaxis = set_vector_length(new_yaxis, y.length)
          new_zaxis = set_vector_length(new_zaxis, z.length)
        end

        from_axes(
          transformation.origin,
          x,
          new_yaxis,
          new_zaxis
        )
      end

      # Get X rotation in radians.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      def rotx(transformation)
        euler_angles(transformation)[0]
      end

      # Get Y rotation in radians.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      def roty(transformation)
        euler_angles(transformation)[1]
      end

      # Get Z rotation in radians.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      def rotz(transformation)
        euler_angles(transformation)[2]
      end

      # Test if two transformations are the same.
      #
      # Uses SketchUp's floating point tolerance.
      #
      # @param tr_a [Geom::Transformation]
      # @param tr_b [Geom::Transformation]
      # @return [Boolean]
      #
      # @example
      #   SupexStdlib::Geom::Transformation.same?(tr1, tr2)
      def same?(tr_a, tr_b)
        xaxis(tr_a) == xaxis(tr_b) &&
          yaxis(tr_a) == yaxis(tr_b) &&
          zaxis(tr_a) == zaxis(tr_b) &&
          tr_a.origin == tr_b.origin
      end

      # Compute the area scale factor of transformation at a specific plane.
      #
      # @param transformation [Geom::Transformation]
      # @param plane [Array] plane as [point, vector] or [a, b, c, d]
      # @return [Float]
      #
      # @example
      #   factor = SupexStdlib::Geom::Transformation.scale_factor_in_plane(tr, [ORIGIN, Z_AXIS])
      def scale_factor_in_plane(transformation, plane)
        normal = Plane.normal(plane)

        tr = from_axes(
          ORIGIN,
          yaxis(transformation) * zaxis(transformation),
          zaxis(transformation) * xaxis(transformation),
          xaxis(transformation) * yaxis(transformation)
        )

        normal.transform(tr).length.to_f
      end

      # Test if transformation is sheared (not orthogonal).
      #
      # @param transformation [Geom::Transformation]
      # @return [Boolean]
      #
      # @example
      #   SupexStdlib::Geom::Transformation.sheared?(tr)
      def sheared?(transformation)
        !xaxis(transformation).parallel?(yaxis(transformation) * zaxis(transformation))
      end

      # Transpose the 3x3 rotation/scale matrix (drops translation).
      #
      # @param transformation [Geom::Transformation]
      # @return [Geom::Transformation]
      #
      # @example
      #   transposed = SupexStdlib::Geom::Transformation.transpose(tr)
      def transpose(transformation)
        a = transformation.to_a

        ::Geom::Transformation.new([
                                     a[0], a[4], a[8], 0,
                                     a[1], a[5], a[9], 0,
                                     a[2], a[6], a[10], 0,
                                     0, 0, 0, a[15]
                                   ])
      end

      # Get X axis vector preserving scale.
      #
      # Unlike native Transformation#xaxis, length represents scaling.
      #
      # @param transformation [Geom::Transformation]
      # @return [Geom::Vector3d]
      def xaxis(transformation)
        a = transformation.to_a
        v = ::Geom::Vector3d.new(a[0], a[1], a[2])
        set_vector_length(v, v.length / a[15])
      end

      # Get X scale factor.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      def xscale(transformation)
        xaxis(transformation).length.to_f
      end

      # Get Y axis vector preserving scale.
      #
      # Unlike native Transformation#yaxis, length represents scaling.
      #
      # @param transformation [Geom::Transformation]
      # @return [Geom::Vector3d]
      def yaxis(transformation)
        a = transformation.to_a
        v = ::Geom::Vector3d.new(a[4], a[5], a[6])
        set_vector_length(v, v.length / a[15])
      end

      # Get Y scale factor.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      def yscale(transformation)
        yaxis(transformation).length.to_f
      end

      # Get Z axis vector preserving scale.
      #
      # Unlike native Transformation#zaxis, length represents scaling.
      #
      # @param transformation [Geom::Transformation]
      # @return [Geom::Vector3d]
      def zaxis(transformation)
        a = transformation.to_a
        v = ::Geom::Vector3d.new(a[8], a[9], a[10])
        set_vector_length(v, v.length / a[15])
      end

      # Get Z scale factor.
      #
      # @param transformation [Geom::Transformation]
      # @return [Float]
      def zscale(transformation)
        zaxis(transformation).length.to_f
      end

      private

      # Set vector to a specific length (workaround for mutable length= in SketchUp)
      def set_vector_length(vector, length)
        return vector unless vector.valid?

        normalized = vector.normalize
        ::Geom::Vector3d.new(normalized.x * length, normalized.y * length, normalized.z * length)
      end
    end
  end
end
