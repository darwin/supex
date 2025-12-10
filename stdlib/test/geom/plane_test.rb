# frozen_string_literal: true

require_relative '../test_helper'

class PlaneTest < Minitest::Test
  # normal tests

  def test_normal_from_point_vector_format
    plane = [ORIGIN, Z_AXIS]
    result = SupexStdlib::Geom::Plane.normal(plane)

    assert_equal Z_AXIS, result
  end

  def test_normal_from_coefficients_format
    plane = [0, 0, 1, 0] # z = 0 plane
    result = SupexStdlib::Geom::Plane.normal(plane)

    assert_in_delta 0.0, result.x, 1e-10
    assert_in_delta 0.0, result.y, 1e-10
    assert_in_delta 1.0, result.z, 1e-10
  end

  def test_normal_is_normalized
    plane = [0, 0, 10, 0] # scaled normal
    result = SupexStdlib::Geom::Plane.normal(plane)

    assert_in_delta 1.0, result.length, 1e-10
  end

  def test_normal_invalid_plane_raises
    assert_raises(ArgumentError) { SupexStdlib::Geom::Plane.normal([1, 2, 3]) }
  end

  # point tests

  def test_point_from_point_vector_format
    pt = Geom::Point3d.new(5, 5, 5)
    plane = [pt, Z_AXIS]
    result = SupexStdlib::Geom::Plane.point(plane)

    assert_equal pt, result
  end

  def test_point_from_coefficients_format
    # Plane equation: x = 5, so [1, 0, 0, -5]
    plane = [1, 0, 0, -5]
    result = SupexStdlib::Geom::Plane.point(plane)

    assert_in_delta 5.0, result.x, 1e-10
  end

  def test_point_is_on_plane
    plane = [0, 0, 1, -10] # z = 10 plane
    result = SupexStdlib::Geom::Plane.point(plane)

    assert result.on_plane?(plane)
  end

  def test_point_invalid_plane_raises
    assert_raises(ArgumentError) { SupexStdlib::Geom::Plane.point('not a plane') }
  end

  # parallel? tests

  def test_parallel_same_normal
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [Geom::Point3d.new(0, 0, 10), Z_AXIS]

    assert SupexStdlib::Geom::Plane.parallel?(plane_a, plane_b)
  end

  def test_parallel_opposite_normals
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [ORIGIN, Z_AXIS.reverse]

    assert SupexStdlib::Geom::Plane.parallel?(plane_a, plane_b)
  end

  def test_not_parallel
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [ORIGIN, X_AXIS]

    refute SupexStdlib::Geom::Plane.parallel?(plane_a, plane_b)
  end

  def test_parallel_different_formats
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [0, 0, 1, -10]

    assert SupexStdlib::Geom::Plane.parallel?(plane_a, plane_b)
  end

  def test_parallel_invalid_plane_raises
    assert_raises(ArgumentError) { SupexStdlib::Geom::Plane.parallel?([1], [ORIGIN, Z_AXIS]) }
  end

  # same? tests

  def test_same_identical_planes
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [ORIGIN, Z_AXIS]

    assert SupexStdlib::Geom::Plane.same?(plane_a, plane_b)
  end

  def test_same_different_points_same_plane
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [Geom::Point3d.new(10, 10, 0), Z_AXIS]

    assert SupexStdlib::Geom::Plane.same?(plane_a, plane_b)
  end

  def test_same_parallel_but_offset
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [Geom::Point3d.new(0, 0, 10), Z_AXIS]

    refute SupexStdlib::Geom::Plane.same?(plane_a, plane_b)
  end

  def test_same_flipped_not_included
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [ORIGIN, Z_AXIS.reverse]

    refute SupexStdlib::Geom::Plane.same?(plane_a, plane_b, false)
  end

  def test_same_flipped_included
    plane_a = [ORIGIN, Z_AXIS]
    plane_b = [ORIGIN, Z_AXIS.reverse]

    assert SupexStdlib::Geom::Plane.same?(plane_a, plane_b, true)
  end

  # transform tests

  def test_transform_translation
    plane = [ORIGIN, Z_AXIS]
    tr = Geom::Transformation.new(Geom::Point3d.new(0, 0, 10))

    result = SupexStdlib::Geom::Plane.transform(plane, tr)

    assert_equal 2, result.size
    assert_in_delta 10.0, result[0].z, 1e-10
    assert_equal Z_AXIS, result[1]
  end

  def test_transform_rotation
    plane = [ORIGIN, Z_AXIS]
    # 90 degree rotation around X axis
    angle = Math::PI / 2
    tr = Geom::Transformation.new([
                                    1, 0, 0, 0,
                                    0, Math.cos(angle), Math.sin(angle), 0,
                                    0, -Math.sin(angle), Math.cos(angle), 0,
                                    0, 0, 0, 1
                                  ])

    result = SupexStdlib::Geom::Plane.transform(plane, tr)

    # Normal should rotate from Z to -Y
    assert_in_delta 0.0, result[1].x, 1e-10
    assert_in_delta(-1.0, result[1].y, 1e-10)
    assert_in_delta 0.0, result[1].z, 1e-10
  end

  def test_transform_returns_point_vector_format
    plane = [0, 0, 1, -5] # z = 5 plane in coefficient format
    tr = Geom::Transformation.new

    result = SupexStdlib::Geom::Plane.transform(plane, tr)

    assert_kind_of Geom::Point3d, result[0]
    assert_kind_of Geom::Vector3d, result[1]
  end

  def test_transform_invalid_plane_raises
    assert_raises(ArgumentError) { SupexStdlib::Geom::Plane.transform([1, 2], Geom::Transformation.new) }
  end

  def test_transform_invalid_transformation_raises
    assert_raises(ArgumentError) { SupexStdlib::Geom::Plane.transform([ORIGIN, Z_AXIS], 'not a tr') }
  end

  # valid? tests

  def test_valid_point_vector_format
    assert SupexStdlib::Geom::Plane.valid?([ORIGIN, Z_AXIS])
  end

  def test_valid_coefficients_format
    assert SupexStdlib::Geom::Plane.valid?([1, 0, 0, -5])
  end

  def test_valid_array_point_and_vector
    # Arrays that represent point and vector
    assert SupexStdlib::Geom::Plane.valid?([[0, 0, 0], [0, 0, 1]])
  end

  def test_invalid_wrong_size
    refute SupexStdlib::Geom::Plane.valid?([1, 2, 3])
  end

  def test_invalid_wrong_type
    refute SupexStdlib::Geom::Plane.valid?('not a plane')
  end

  def test_invalid_nil
    refute SupexStdlib::Geom::Plane.valid?(nil)
  end

  def test_invalid_mixed_types
    refute SupexStdlib::Geom::Plane.valid?([ORIGIN, 1, 2, 3])
  end
end
