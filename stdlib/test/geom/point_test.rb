# frozen_string_literal: true

require_relative '../test_helper'

class PointTest < Minitest::Test
  def test_between_point_in_middle
    boundary_a = Geom::Point3d.new(0, 0, 0)
    boundary_b = Geom::Point3d.new(10, 0, 0)
    point = Geom::Point3d.new(5, 0, 0)

    assert SupexStdlib::Geom::Point.between?(point, boundary_a, boundary_b)
  end

  def test_between_point_outside
    boundary_a = Geom::Point3d.new(0, 0, 0)
    boundary_b = Geom::Point3d.new(10, 0, 0)
    point = Geom::Point3d.new(15, 0, 0)

    refute SupexStdlib::Geom::Point.between?(point, boundary_a, boundary_b)
  end

  def test_between_point_on_boundary_included
    boundary_a = Geom::Point3d.new(0, 0, 0)
    boundary_b = Geom::Point3d.new(10, 0, 0)

    assert SupexStdlib::Geom::Point.between?(boundary_a, boundary_a, boundary_b, true)
    assert SupexStdlib::Geom::Point.between?(boundary_b, boundary_a, boundary_b, true)
  end

  def test_between_point_on_boundary_excluded
    boundary_a = Geom::Point3d.new(0, 0, 0)
    boundary_b = Geom::Point3d.new(10, 0, 0)

    refute SupexStdlib::Geom::Point.between?(boundary_a, boundary_a, boundary_b, false)
    refute SupexStdlib::Geom::Point.between?(boundary_b, boundary_a, boundary_b, false)
  end

  def test_between_point_not_on_line
    boundary_a = Geom::Point3d.new(0, 0, 0)
    boundary_b = Geom::Point3d.new(10, 0, 0)
    point = Geom::Point3d.new(5, 5, 0) # off the line

    refute SupexStdlib::Geom::Point.between?(point, boundary_a, boundary_b)
  end

  def test_front_of_plane_in_front
    point = Geom::Point3d.new(0, 0, 5)
    plane = [ORIGIN, Z_AXIS]

    assert SupexStdlib::Geom::Point.front_of_plane?(point, plane)
  end

  def test_front_of_plane_behind
    point = Geom::Point3d.new(0, 0, -5)
    plane = [ORIGIN, Z_AXIS]

    refute SupexStdlib::Geom::Point.front_of_plane?(point, plane)
  end

  def test_front_of_plane_on_plane
    point = Geom::Point3d.new(5, 5, 0)
    plane = [ORIGIN, Z_AXIS]

    refute SupexStdlib::Geom::Point.front_of_plane?(point, plane)
  end
end
