# frozen_string_literal: true

require_relative 'test_helper'

class GeomTest < Minitest::Test
  def test_mid_point_with_two_points
    pt1 = Geom::Point3d.new(0, 0, 0)
    pt2 = Geom::Point3d.new(10, 10, 10)

    mid = SupexStdlib::Geom.mid_point(pt1, pt2)

    assert_equal 5.0, mid.x
    assert_equal 5.0, mid.y
    assert_equal 5.0, mid.z
  end

  def test_mid_point_with_negative_coordinates
    pt1 = Geom::Point3d.new(-10, 0, 5)
    pt2 = Geom::Point3d.new(10, 20, 15)

    mid = SupexStdlib::Geom.mid_point(pt1, pt2)

    assert_equal 0.0, mid.x
    assert_equal 10.0, mid.y
    assert_equal 10.0, mid.z
  end

  def test_offset_points
    points = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0),
      Geom::Point3d.new(10, 10, 0)
    ]
    vector = Geom::Vector3d.new(0, 0, 5)

    result = SupexStdlib::Geom.offset_points(points, vector)

    assert_equal 3, result.size
    assert_equal 5.0, result[0].z
    assert_equal 5.0, result[1].z
    assert_equal 5.0, result[2].z
  end

  def test_polygon_normal_triangle
    # Counter-clockwise triangle in XY plane
    points = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0),
      Geom::Point3d.new(5, 10, 0)
    ]

    normal = SupexStdlib::Geom.polygon_normal(points)

    assert_in_delta 0.0, normal.x, 1e-10
    assert_in_delta 0.0, normal.y, 1e-10
    assert_in_delta 1.0, normal.z.abs, 1e-10
  end

  def test_polygon_normal_square
    points = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0),
      Geom::Point3d.new(10, 10, 0),
      Geom::Point3d.new(0, 10, 0)
    ]

    normal = SupexStdlib::Geom.polygon_normal(points)

    assert_in_delta 0.0, normal.x, 1e-10
    assert_in_delta 0.0, normal.y, 1e-10
    assert_in_delta 1.0, normal.z.abs, 1e-10
  end

  def test_polygon_area_square
    points = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0),
      Geom::Point3d.new(10, 10, 0),
      Geom::Point3d.new(0, 10, 0)
    ]

    area = SupexStdlib::Geom.polygon_area(points)

    assert_in_delta 100.0, area, 1e-6
  end

  def test_polygon_area_triangle
    points = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0),
      Geom::Point3d.new(0, 10, 0)
    ]

    area = SupexStdlib::Geom.polygon_area(points)

    assert_in_delta 50.0, area, 1e-6
  end

  def test_remove_duplicates
    pt1 = Geom::Point3d.new(0, 0, 0)
    pt2 = Geom::Point3d.new(10, 0, 0)
    pt3 = Geom::Point3d.new(0, 0, 0) # duplicate of pt1

    result = SupexStdlib::Geom.remove_duplicates([pt1, pt2, pt3])

    assert_equal 2, result.size
  end

  def test_angle_in_plane_same_direction
    v1 = Geom::Vector3d.new(1, 0, 0)
    v2 = Geom::Vector3d.new(1, 0, 0)

    angle = SupexStdlib::Geom.angle_in_plane(v1, v2, Z_AXIS)

    assert_in_delta 0.0, angle, 1e-10
  end

  def test_angle_in_plane_90_degrees
    v1 = Geom::Vector3d.new(0, 1, 0)
    v2 = Geom::Vector3d.new(1, 0, 0)

    angle = SupexStdlib::Geom.angle_in_plane(v1, v2, Z_AXIS)

    assert_in_delta Math::PI / 2, angle, 1e-10
  end

  def test_angle_in_plane_180_degrees
    v1 = Geom::Vector3d.new(-1, 0, 0)
    v2 = Geom::Vector3d.new(1, 0, 0)

    angle = SupexStdlib::Geom.angle_in_plane(v1, v2, Z_AXIS)

    assert_in_delta Math::PI, angle, 1e-10
  end

  def test_angle_in_plane_270_degrees
    v1 = Geom::Vector3d.new(0, -1, 0)
    v2 = Geom::Vector3d.new(1, 0, 0)

    angle = SupexStdlib::Geom.angle_in_plane(v1, v2, Z_AXIS)

    assert_in_delta Math::PI * 1.5, angle, 1e-10
  end
end
