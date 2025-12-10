# frozen_string_literal: true

require_relative '../test_helper'

class VectorTest < Minitest::Test
  def test_arbitrary_non_parallel_to_z
    result = SupexStdlib::Geom::Vector.arbitrary_non_parallel(Z_AXIS)

    refute result.parallel?(Z_AXIS)
    assert_equal X_AXIS, result
  end

  def test_arbitrary_non_parallel_to_x
    result = SupexStdlib::Geom::Vector.arbitrary_non_parallel(X_AXIS)

    refute result.parallel?(X_AXIS)
    assert_equal Z_AXIS, result
  end

  def test_arbitrary_non_parallel_to_y
    result = SupexStdlib::Geom::Vector.arbitrary_non_parallel(Y_AXIS)

    refute result.parallel?(Y_AXIS)
    assert_equal Z_AXIS, result
  end

  def test_arbitrary_non_parallel_to_diagonal
    diagonal = Geom::Vector3d.new(1, 1, 0).normalize

    result = SupexStdlib::Geom::Vector.arbitrary_non_parallel(diagonal)

    refute result.parallel?(diagonal)
  end

  def test_arbitrary_perpendicular_to_z
    result = SupexStdlib::Geom::Vector.arbitrary_perpendicular(Z_AXIS)

    assert_in_delta 0.0, result % Z_AXIS, 1e-10
    assert_in_delta 1.0, result.length, 1e-10
  end

  def test_arbitrary_perpendicular_to_x
    result = SupexStdlib::Geom::Vector.arbitrary_perpendicular(X_AXIS)

    assert_in_delta 0.0, result % X_AXIS, 1e-10
    assert_in_delta 1.0, result.length, 1e-10
  end

  def test_arbitrary_perpendicular_to_diagonal
    diagonal = Geom::Vector3d.new(1, 1, 1).normalize
    result = SupexStdlib::Geom::Vector.arbitrary_perpendicular(diagonal)

    assert_in_delta 0.0, result % diagonal, 1e-10
    assert_in_delta 1.0, result.length, 1e-10
  end

  def test_transform_as_normal_identity
    normal = Z_AXIS
    tr = Geom::Transformation.new

    result = SupexStdlib::Geom::Vector.transform_as_normal(normal, tr)

    assert_in_delta 0.0, result.x, 1e-10
    assert_in_delta 0.0, result.y, 1e-10
    assert_in_delta 1.0, result.z.abs, 1e-10
  end

  def test_transform_as_normal_rotation
    normal = Z_AXIS
    # 90 degree rotation around X axis
    angle = Math::PI / 2
    tr = Geom::Transformation.new([
                                    1, 0, 0, 0,
                                    0, Math.cos(angle), Math.sin(angle), 0,
                                    0, -Math.sin(angle), Math.cos(angle), 0,
                                    0, 0, 0, 1
                                  ])

    result = SupexStdlib::Geom::Vector.transform_as_normal(normal, tr)

    # Z axis rotated 90 degrees around X becomes -Y axis
    assert_in_delta 0.0, result.x, 1e-10
    assert_in_delta(-1.0, result.y, 1e-10)
    assert_in_delta 0.0, result.z, 1e-10
  end

  def test_transform_as_normal_non_uniform_scale
    normal = Geom::Vector3d.new(1, 1, 0).normalize
    # Non-uniform scale: 2x in X, 1x in Y, 1x in Z
    tr = Geom::Transformation.new([
                                    2, 0, 0, 0,
                                    0, 1, 0, 0,
                                    0, 0, 1, 0,
                                    0, 0, 0, 1
                                  ])

    result = SupexStdlib::Geom::Vector.transform_as_normal(normal, tr)

    # For non-uniform scaling, normal transforms differently than regular vectors
    # The result should still be normalized
    assert_in_delta 1.0, result.length, 1e-10
  end
end
