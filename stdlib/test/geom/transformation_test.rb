# frozen_string_literal: true

require_relative '../test_helper'

class TransformationTest < Minitest::Test
  # from_axes tests

  def test_from_axes_identity
    tr = SupexStdlib::Geom::Transformation.from_axes(ORIGIN, X_AXIS, Y_AXIS, Z_AXIS)

    assert SupexStdlib::Geom::Transformation.identity?(tr)
  end

  def test_from_axes_translated
    origin = Geom::Point3d.new(10, 20, 30)
    tr = SupexStdlib::Geom::Transformation.from_axes(origin, X_AXIS, Y_AXIS, Z_AXIS)

    assert_equal origin, tr.origin
  end

  def test_from_axes_scaled
    tr = SupexStdlib::Geom::Transformation.from_axes(
      ORIGIN,
      Geom::Vector3d.new(2, 0, 0),
      Geom::Vector3d.new(0, 3, 0),
      Geom::Vector3d.new(0, 0, 4)
    )

    assert_in_delta 2.0, SupexStdlib::Geom::Transformation.xscale(tr), 1e-10
    assert_in_delta 3.0, SupexStdlib::Geom::Transformation.yscale(tr), 1e-10
    assert_in_delta 4.0, SupexStdlib::Geom::Transformation.zscale(tr), 1e-10
  end

  def test_from_axes_zero_length_raises
    assert_raises(ArgumentError) do
      SupexStdlib::Geom::Transformation.from_axes(
        ORIGIN,
        Geom::Vector3d.new(0, 0, 0),
        Y_AXIS,
        Z_AXIS
      )
    end
  end

  def test_from_axes_parallel_raises
    assert_raises(ArgumentError) do
      SupexStdlib::Geom::Transformation.from_axes(
        ORIGIN,
        X_AXIS,
        X_AXIS,
        Z_AXIS
      )
    end
  end

  # from_euler_angles tests

  def test_from_euler_angles_zero_is_identity
    tr = SupexStdlib::Geom::Transformation.from_euler_angles(ORIGIN, 0, 0, 0)

    assert SupexStdlib::Geom::Transformation.identity?(tr)
  end

  def test_from_euler_angles_with_translation
    origin = Geom::Point3d.new(5, 5, 5)
    tr = SupexStdlib::Geom::Transformation.from_euler_angles(origin, 0, 0, 0)

    assert_equal origin, tr.origin
  end

  def test_from_euler_angles_roundtrip
    x_angle = 0.5
    y_angle = 0.3
    z_angle = 0.1

    tr = SupexStdlib::Geom::Transformation.from_euler_angles(ORIGIN, x_angle, y_angle, z_angle)
    angles = SupexStdlib::Geom::Transformation.euler_angles(tr)

    assert_in_delta x_angle, angles[0], 1e-10
    assert_in_delta y_angle, angles[1], 1e-10
    assert_in_delta z_angle, angles[2], 1e-10
  end

  # determinant tests

  def test_determinant_identity
    det = SupexStdlib::Geom::Transformation.determinant(IDENTITY)

    assert_in_delta 1.0, det, 1e-10
  end

  def test_determinant_scaled
    tr = Geom::Transformation.scaling(ORIGIN, 2, 2, 2)
    det = SupexStdlib::Geom::Transformation.determinant(tr)

    assert_in_delta 8.0, det, 1e-10
  end

  def test_determinant_flipped
    tr = Geom::Transformation.scaling(ORIGIN, -1, 1, 1)
    det = SupexStdlib::Geom::Transformation.determinant(tr)

    assert det < 0
  end

  # euler_angles tests

  def test_euler_angles_identity
    angles = SupexStdlib::Geom::Transformation.euler_angles(IDENTITY)

    assert_in_delta 0.0, angles[0], 1e-10
    assert_in_delta 0.0, angles[1], 1e-10
    assert_in_delta 0.0, angles[2], 1e-10
  end

  # flipped? tests

  def test_flipped_identity_is_false
    refute SupexStdlib::Geom::Transformation.flipped?(IDENTITY)
  end

  def test_flipped_mirrored_is_true
    tr = Geom::Transformation.scaling(ORIGIN, -1, 1, 1)

    assert SupexStdlib::Geom::Transformation.flipped?(tr)
  end

  def test_flipped_double_mirror_is_false
    tr = Geom::Transformation.scaling(ORIGIN, -1, -1, 1)

    refute SupexStdlib::Geom::Transformation.flipped?(tr)
  end

  # identity? tests

  def test_identity_on_identity
    assert SupexStdlib::Geom::Transformation.identity?(IDENTITY)
  end

  def test_identity_on_translation
    tr = Geom::Transformation.new(Geom::Point3d.new(1, 0, 0))

    refute SupexStdlib::Geom::Transformation.identity?(tr)
  end

  def test_identity_on_rotation
    tr = Geom::Transformation.rotation(ORIGIN, Z_AXIS, 0.1)

    refute SupexStdlib::Geom::Transformation.identity?(tr)
  end

  # remove_scaling tests

  def test_remove_scaling_from_scaled
    tr = Geom::Transformation.scaling(ORIGIN, 2, 3, 4)
    result = SupexStdlib::Geom::Transformation.remove_scaling(tr)

    assert_in_delta 1.0, SupexStdlib::Geom::Transformation.xscale(result), 1e-10
    assert_in_delta 1.0, SupexStdlib::Geom::Transformation.yscale(result), 1e-10
    assert_in_delta 1.0, SupexStdlib::Geom::Transformation.zscale(result), 1e-10
  end

  def test_remove_scaling_preserves_origin
    origin = Geom::Point3d.new(5, 5, 5)
    tr = SupexStdlib::Geom::Transformation.from_axes(
      origin,
      Geom::Vector3d.new(2, 0, 0),
      Geom::Vector3d.new(0, 2, 0),
      Geom::Vector3d.new(0, 0, 2)
    )
    result = SupexStdlib::Geom::Transformation.remove_scaling(tr)

    assert_equal origin, result.origin
  end

  # remove_shearing tests

  def test_remove_shearing_from_orthogonal
    result = SupexStdlib::Geom::Transformation.remove_shearing(IDENTITY)

    assert SupexStdlib::Geom::Transformation.identity?(result)
  end

  def test_remove_shearing_makes_orthogonal
    sheared = SupexStdlib::Geom::Transformation.from_axes(
      ORIGIN,
      X_AXIS,
      Geom::Vector3d.new(0.5, 1, 0),
      Z_AXIS
    )
    result = SupexStdlib::Geom::Transformation.remove_shearing(sheared)

    refute SupexStdlib::Geom::Transformation.sheared?(result)
  end

  # rotx, roty, rotz tests

  def test_rotx
    angle = SupexStdlib::Geom::Transformation.rotx(IDENTITY)

    assert_in_delta 0.0, angle, 1e-10
  end

  def test_roty
    angle = SupexStdlib::Geom::Transformation.roty(IDENTITY)

    assert_in_delta 0.0, angle, 1e-10
  end

  def test_rotz
    angle = SupexStdlib::Geom::Transformation.rotz(IDENTITY)

    assert_in_delta 0.0, angle, 1e-10
  end

  # same? tests

  def test_same_identical
    assert SupexStdlib::Geom::Transformation.same?(IDENTITY, IDENTITY)
  end

  def test_same_equivalent
    tr1 = Geom::Transformation.new
    tr2 = Geom::Transformation.new

    assert SupexStdlib::Geom::Transformation.same?(tr1, tr2)
  end

  def test_same_different
    tr1 = IDENTITY
    tr2 = Geom::Transformation.new(Geom::Point3d.new(1, 0, 0))

    refute SupexStdlib::Geom::Transformation.same?(tr1, tr2)
  end

  # scale_factor_in_plane tests

  def test_scale_factor_in_plane_identity
    factor = SupexStdlib::Geom::Transformation.scale_factor_in_plane(IDENTITY, [ORIGIN, Z_AXIS])

    assert_in_delta 1.0, factor, 1e-10
  end

  def test_scale_factor_in_plane_uniform_scale
    tr = Geom::Transformation.scaling(ORIGIN, 2, 2, 2)
    factor = SupexStdlib::Geom::Transformation.scale_factor_in_plane(tr, [ORIGIN, Z_AXIS])

    assert_in_delta 4.0, factor, 1e-10
  end

  def test_scale_factor_in_plane_non_uniform
    tr = Geom::Transformation.scaling(ORIGIN, 2, 1, 1)
    factor = SupexStdlib::Geom::Transformation.scale_factor_in_plane(tr, [ORIGIN, Z_AXIS])

    assert_in_delta 2.0, factor, 1e-10
  end

  # sheared? tests

  def test_sheared_identity_is_false
    refute SupexStdlib::Geom::Transformation.sheared?(IDENTITY)
  end

  def test_sheared_with_shear_is_true
    sheared = SupexStdlib::Geom::Transformation.from_axes(
      ORIGIN,
      X_AXIS,
      Geom::Vector3d.new(0.5, 1, 0),
      Z_AXIS
    )

    assert SupexStdlib::Geom::Transformation.sheared?(sheared)
  end

  def test_sheared_scaled_is_false
    tr = Geom::Transformation.scaling(ORIGIN, 2, 3, 4)

    refute SupexStdlib::Geom::Transformation.sheared?(tr)
  end

  # transpose tests

  def test_transpose_identity
    result = SupexStdlib::Geom::Transformation.transpose(IDENTITY)

    assert SupexStdlib::Geom::Transformation.identity?(result)
  end

  def test_transpose_drops_translation
    tr = Geom::Transformation.new(Geom::Point3d.new(10, 20, 30))
    result = SupexStdlib::Geom::Transformation.transpose(tr)

    assert_equal ORIGIN, result.origin
  end

  # xaxis, yaxis, zaxis tests

  def test_xaxis_identity
    axis = SupexStdlib::Geom::Transformation.xaxis(IDENTITY)

    assert_equal X_AXIS, axis
  end

  def test_yaxis_identity
    axis = SupexStdlib::Geom::Transformation.yaxis(IDENTITY)

    assert_equal Y_AXIS, axis
  end

  def test_zaxis_identity
    axis = SupexStdlib::Geom::Transformation.zaxis(IDENTITY)

    assert_equal Z_AXIS, axis
  end

  def test_xaxis_scaled
    tr = Geom::Transformation.scaling(ORIGIN, 2, 1, 1)
    axis = SupexStdlib::Geom::Transformation.xaxis(tr)

    assert_in_delta 2.0, axis.length, 1e-10
  end

  # xscale, yscale, zscale tests

  def test_xscale_identity
    scale = SupexStdlib::Geom::Transformation.xscale(IDENTITY)

    assert_in_delta 1.0, scale, 1e-10
  end

  def test_yscale_scaled
    tr = Geom::Transformation.scaling(ORIGIN, 1, 3, 1)
    scale = SupexStdlib::Geom::Transformation.yscale(tr)

    assert_in_delta 3.0, scale, 1e-10
  end

  def test_zscale_scaled
    tr = Geom::Transformation.scaling(ORIGIN, 1, 1, 5)
    scale = SupexStdlib::Geom::Transformation.zscale(tr)

    assert_in_delta 5.0, scale, 1e-10
  end

  # extract_shearing tests

  def test_extract_shearing_from_orthogonal
    shear = SupexStdlib::Geom::Transformation.extract_shearing(IDENTITY)

    # Should be close to identity when no shearing
    assert SupexStdlib::Geom::Transformation.identity?(shear)
  end
end
