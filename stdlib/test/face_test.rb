# frozen_string_literal: true

require_relative 'test_helper'

class FaceTest < Minitest::Test
  def setup
    @face = Sketchup::Face.new
    # Setup a simple triangular mesh
    @face.mesh.points = [
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0),
      Geom::Point3d.new(5, 10, 0)
    ]
    @face.mesh.polygons = [[1, 2, 3]]
  end

  # Module existence tests

  def test_module_exists
    assert defined?(SupexStdlib::Face)
  end

  def test_responds_to_arbitrary_interior_point
    assert_respond_to SupexStdlib::Face, :arbitrary_interior_point
  end

  def test_responds_to_includes_point
    assert_respond_to SupexStdlib::Face, :includes_point?
  end

  def test_responds_to_inner_loops
    assert_respond_to SupexStdlib::Face, :inner_loops
  end

  def test_responds_to_triangulate
    assert_respond_to SupexStdlib::Face, :triangulate
  end

  def test_responds_to_wrapping_face
    assert_respond_to SupexStdlib::Face, :wrapping_face
  end

  # inner_loops tests

  def test_inner_loops_empty_when_no_holes
    result = SupexStdlib::Face.inner_loops(@face)

    assert_empty result
  end

  def test_inner_loops_returns_loops_excluding_outer
    inner_loop = Sketchup::Loop.new
    @face.loops << inner_loop

    result = SupexStdlib::Face.inner_loops(@face)

    assert_equal 1, result.size
    assert_equal inner_loop, result.first
    refute_includes result, @face.outer_loop
  end

  # includes_point? tests

  def test_includes_point_inside
    point = Geom::Point3d.new(5, 5, 0)

    assert SupexStdlib::Face.includes_point?(@face, point)
  end

  # triangulate tests

  def test_triangulate_returns_triangles
    result = SupexStdlib::Face.triangulate(@face)

    assert_kind_of Array, result
  end

  # arbitrary_interior_point tests

  def test_arbitrary_interior_point_returns_nil_for_zero_area
    @face.area = 0

    result = SupexStdlib::Face.arbitrary_interior_point(@face)

    assert_nil result
  end

  # wrapping_face tests

  def test_wrapping_face_returns_nil_when_not_wrapped
    result = SupexStdlib::Face.wrapping_face(@face)

    assert_nil result
  end
end
