# frozen_string_literal: true

require_relative 'test_helper'

class EdgeTest < Minitest::Test
  def setup
    @start_pos = Geom::Point3d.new(0, 0, 0)
    @end_pos = Geom::Point3d.new(10, 0, 0)
    @edge = Sketchup::Edge.new(@start_pos, @end_pos)
  end

  # Module existence tests

  def test_module_exists
    assert defined?(SupexStdlib::Edge)
  end

  def test_responds_to_midpoint
    assert_respond_to SupexStdlib::Edge, :midpoint
  end

  def test_responds_to_length
    assert_respond_to SupexStdlib::Edge, :length
  end

  def test_responds_to_direction
    assert_respond_to SupexStdlib::Edge, :direction
  end

  def test_responds_to_parallel
    assert_respond_to SupexStdlib::Edge, :parallel?
  end

  def test_responds_to_to_line
    assert_respond_to SupexStdlib::Edge, :to_line
  end

  # midpoint tests

  def test_midpoint
    result = SupexStdlib::Edge.midpoint(@edge)

    assert_in_delta 5.0, result.x, 1e-10
    assert_in_delta 0.0, result.y, 1e-10
    assert_in_delta 0.0, result.z, 1e-10
  end

  def test_midpoint_diagonal
    edge = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 10, 10)
    )

    result = SupexStdlib::Edge.midpoint(edge)

    assert_in_delta 5.0, result.x, 1e-10
    assert_in_delta 5.0, result.y, 1e-10
    assert_in_delta 5.0, result.z, 1e-10
  end

  # length tests

  def test_length
    result = SupexStdlib::Edge.length(@edge)

    assert_in_delta 10.0, result, 1e-10
  end

  def test_length_diagonal
    edge = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(3, 4, 0)
    )

    result = SupexStdlib::Edge.length(edge)

    assert_in_delta 5.0, result, 1e-10
  end

  # direction tests

  def test_direction
    result = SupexStdlib::Edge.direction(@edge)

    assert_in_delta 1.0, result.x, 1e-10
    assert_in_delta 0.0, result.y, 1e-10
    assert_in_delta 0.0, result.z, 1e-10
  end

  def test_direction_is_normalized
    edge = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(100, 0, 0)
    )

    result = SupexStdlib::Edge.direction(edge)

    assert_in_delta 1.0, result.length, 1e-10
  end

  # parallel? tests

  def test_parallel_same_direction
    edge1 = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0)
    )
    edge2 = Sketchup::Edge.new(
      Geom::Point3d.new(0, 5, 0),
      Geom::Point3d.new(10, 5, 0)
    )

    assert SupexStdlib::Edge.parallel?(edge1, edge2)
  end

  def test_parallel_opposite_direction
    edge1 = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0)
    )
    edge2 = Sketchup::Edge.new(
      Geom::Point3d.new(10, 5, 0),
      Geom::Point3d.new(0, 5, 0)
    )

    assert SupexStdlib::Edge.parallel?(edge1, edge2)
  end

  def test_not_parallel
    edge1 = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(10, 0, 0)
    )
    edge2 = Sketchup::Edge.new(
      Geom::Point3d.new(0, 0, 0),
      Geom::Point3d.new(0, 10, 0)
    )

    refute SupexStdlib::Edge.parallel?(edge1, edge2)
  end

  # to_line tests

  def test_to_line
    result = SupexStdlib::Edge.to_line(@edge)

    assert_kind_of Array, result
    assert_equal 2, result.size
    assert_equal @start_pos, result[0]
    assert_in_delta 1.0, result[1].length, 1e-10
  end
end
