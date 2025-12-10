# frozen_string_literal: true

require_relative '../test_helper'

class BoundingBoxTest < Minitest::Test
  include SupexStdlib::Geom::BoundingBoxConstants

  def setup
    # Create standard 8-point bounding box: 10x20x30 at origin
    @corners_3d = [
      Geom::Point3d.new(0, 0, 0),   # BOTTOM_FRONT_LEFT
      Geom::Point3d.new(10, 0, 0),  # BOTTOM_FRONT_RIGHT
      Geom::Point3d.new(10, 20, 0), # BOTTOM_BACK_RIGHT
      Geom::Point3d.new(0, 20, 0),  # BOTTOM_BACK_LEFT
      Geom::Point3d.new(0, 0, 30),  # TOP_FRONT_LEFT
      Geom::Point3d.new(10, 0, 30), # TOP_FRONT_RIGHT
      Geom::Point3d.new(10, 20, 30), # TOP_BACK_RIGHT
      Geom::Point3d.new(0, 20, 30) # TOP_BACK_LEFT
    ]

    # Create 4-point bounding box (2D): 10x20 at origin
    @corners_2d = [
      Geom::Point3d.new(0, 0, 0),   # BOTTOM_FRONT_LEFT
      Geom::Point3d.new(10, 0, 0),  # BOTTOM_FRONT_RIGHT
      Geom::Point3d.new(10, 20, 0), # BOTTOM_BACK_RIGHT
      Geom::Point3d.new(0, 20, 0)   # BOTTOM_BACK_LEFT
    ]
  end

  # Constants tests

  def test_constants
    assert_equal 0, BOTTOM_FRONT_LEFT
    assert_equal 1, BOTTOM_FRONT_RIGHT
    assert_equal 2, BOTTOM_BACK_RIGHT
    assert_equal 3, BOTTOM_BACK_LEFT
    assert_equal 4, TOP_FRONT_LEFT
    assert_equal 5, TOP_FRONT_RIGHT
    assert_equal 6, TOP_BACK_RIGHT
    assert_equal 7, TOP_BACK_LEFT
  end

  # Constructor tests

  def test_new_with_empty_array
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert bb.empty?
  end

  def test_new_with_4_points
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)

    assert bb.is_2d?
    refute bb.is_3d?
  end

  def test_new_with_8_points
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert bb.is_3d?
    refute bb.is_2d?
  end

  def test_new_with_invalid_count_raises
    assert_raises(ArgumentError) { SupexStdlib::Geom::BoundingBox.new([ORIGIN]) }
    assert_raises(ArgumentError) { SupexStdlib::Geom::BoundingBox.new([ORIGIN] * 5) }
  end

  # empty? tests

  def test_empty_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert bb.empty?
  end

  def test_empty_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    refute bb.empty?
  end

  # have_area? tests

  def test_have_area_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    refute bb.have_area?
  end

  def test_have_area_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)

    assert bb.have_area?
  end

  def test_have_area_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert bb.have_area?
  end

  # have_volume? tests

  def test_have_volume_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    refute bb.have_volume?
  end

  def test_have_volume_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)

    refute bb.have_volume?
  end

  def test_have_volume_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert bb.have_volume?
  end

  # Dimension tests

  def test_width_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert_equal 0.0, bb.width
  end

  def test_width_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 10.0, bb.width, 1e-10
  end

  def test_height_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 20.0, bb.height, 1e-10
  end

  def test_depth_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 30.0, bb.depth, 1e-10
  end

  def test_depth_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)

    assert_equal 0.0, bb.depth
  end

  # origin tests

  def test_origin_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert_nil bb.origin
  end

  def test_origin_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_equal ORIGIN, bb.origin
  end

  # Axis tests

  def test_x_axis
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 10.0, bb.x_axis.x, 1e-10
    assert_in_delta 0.0, bb.x_axis.y, 1e-10
    assert_in_delta 0.0, bb.x_axis.z, 1e-10
  end

  def test_y_axis
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 0.0, bb.y_axis.x, 1e-10
    assert_in_delta 20.0, bb.y_axis.y, 1e-10
    assert_in_delta 0.0, bb.y_axis.z, 1e-10
  end

  def test_z_axis
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 0.0, bb.z_axis.x, 1e-10
    assert_in_delta 0.0, bb.z_axis.y, 1e-10
    assert_in_delta 30.0, bb.z_axis.z, 1e-10
  end

  def test_z_axis_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)
    axis = bb.z_axis

    assert_in_delta 0.0, axis.length, 1e-10
  end

  # center tests

  def test_center_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert_nil bb.center
  end

  def test_center_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)
    center = bb.center

    assert_in_delta 5.0, center.x, 1e-10
    assert_in_delta 10.0, center.y, 1e-10
    assert_in_delta 15.0, center.z, 1e-10
  end

  def test_center_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)
    center = bb.center

    assert_in_delta 5.0, center.x, 1e-10
    assert_in_delta 10.0, center.y, 1e-10
    assert_in_delta 0.0, center.z, 1e-10
  end

  # volume tests

  def test_volume_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert_equal 0.0, bb.volume
  end

  def test_volume_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)

    assert_equal 0.0, bb.volume
  end

  def test_volume_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 6000.0, bb.volume, 1e-10 # 10 * 20 * 30
  end

  # area tests

  def test_area_on_empty
    bb = SupexStdlib::Geom::BoundingBox.new([])

    assert_equal 0.0, bb.area
  end

  def test_area_on_2d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_2d)

    assert_in_delta 200.0, bb.area, 1e-10  # 10 * 20
  end

  def test_area_on_3d
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_in_delta 200.0, bb.area, 1e-10  # 10 * 20
  end

  # corner tests

  def test_corner
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_equal @corners_3d[0], bb.corner(0)
    assert_equal @corners_3d[7], bb.corner(7)
  end

  def test_corner_invalid_index
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_nil bb.corner(10)
  end

  # inspect tests

  def test_inspect
    bb = SupexStdlib::Geom::BoundingBox.new(@corners_3d)

    assert_includes bb.inspect, 'BoundingBox'
    assert_includes bb.inspect, '8'
  end
end
