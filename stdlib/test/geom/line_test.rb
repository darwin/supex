# frozen_string_literal: true

require_relative '../test_helper'

class LineTest < Minitest::Test
  def test_new_with_point_and_vector
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    assert_equal ORIGIN, line[0]
    assert_equal Z_AXIS, line[1]
  end

  def test_new_with_two_points
    pt1 = Geom::Point3d.new(0, 0, 0)
    pt2 = Geom::Point3d.new(10, 0, 0)
    line = SupexStdlib::Geom::Line.new(pt1, pt2)

    assert_equal pt1, line[0]
    assert_equal pt2, line[1]
  end

  def test_direction_from_vector
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    direction = line.direction

    assert_equal Z_AXIS, direction
  end

  def test_direction_from_two_points
    pt1 = Geom::Point3d.new(0, 0, 0)
    pt2 = Geom::Point3d.new(10, 0, 0)
    line = SupexStdlib::Geom::Line.new(pt1, pt2)

    direction = line.direction

    assert_equal X_AXIS, direction
  end

  def test_direction_normalized
    pt1 = Geom::Point3d.new(0, 0, 0)
    pt2 = Geom::Point3d.new(100, 0, 0)
    line = SupexStdlib::Geom::Line.new(pt1, pt2)

    direction = line.direction

    assert_in_delta 1.0, direction.length, 1e-10
  end

  def test_direction_cached
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    direction1 = line.direction
    direction2 = line.direction

    assert_same direction1, direction2
  end

  def test_to_a
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    result = line.to_a

    assert_kind_of Array, result
    assert_equal 2, result.size
    assert_equal ORIGIN, result[0]
    assert_equal Z_AXIS, result[1]
  end

  def test_to_a_returns_cloned_point
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    result = line.to_a

    refute_same line[0], result[0]
  end

  def test_valid_with_point_and_vector
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    assert line.valid?
  end

  def test_valid_with_two_points
    pt1 = Geom::Point3d.new(0, 0, 0)
    pt2 = Geom::Point3d.new(10, 0, 0)
    line = SupexStdlib::Geom::Line.new(pt1, pt2)

    assert line.valid?
  end

  def test_valid_with_array_coordinates
    line = SupexStdlib::Geom::Line.new([0, 0, 0], [1, 0, 0])

    assert line.valid?
  end

  def test_inspect
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    result = line.inspect

    assert_includes result, 'Line'
  end

  def test_immutability_push_is_private
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    assert_raises(NoMethodError) { line.push(X_AXIS) }
  end

  def test_immutability_assignment_is_private
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    assert_raises(NoMethodError) { line[0] = X_AXIS }
  end

  def test_is_array_subclass
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    assert_kind_of Array, line
  end

  def test_size_is_two
    line = SupexStdlib::Geom::Line.new(ORIGIN, Z_AXIS)

    assert_equal 2, line.size
  end
end
