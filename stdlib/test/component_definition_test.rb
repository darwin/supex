# frozen_string_literal: true

require_relative 'test_helper'

class ComponentDefinitionTest < Minitest::Test
  # Module existence tests

  def test_module_exists
    assert defined?(SupexStdlib::ComponentDefinition)
  end

  def test_responds_to_erase
    assert_respond_to SupexStdlib::ComponentDefinition, :erase
  end

  def test_responds_to_place_axes
    assert_respond_to SupexStdlib::ComponentDefinition, :place_axes
  end

  def test_responds_to_unique_to
    assert_respond_to SupexStdlib::ComponentDefinition, :unique_to?
  end

  def test_responds_to_all_instance_paths
    assert_respond_to SupexStdlib::ComponentDefinition, :all_instance_paths
  end

  # unique_to? argument validation tests

  def test_unique_to_raises_on_non_definition
    assert_raises(ArgumentError) do
      SupexStdlib::ComponentDefinition.unique_to?('not a definition', [])
    end
  end

  def test_unique_to_raises_on_empty_scopes
    definition = Sketchup::ComponentDefinition.new('Test')

    assert_raises(ArgumentError) do
      SupexStdlib::ComponentDefinition.unique_to?(definition, [])
    end
  end

  # all_instance_paths tests

  def test_all_instance_paths_empty_definition
    definition = Sketchup::ComponentDefinition.new('Test')
    definition.instances = []

    result = SupexStdlib::ComponentDefinition.all_instance_paths(definition)

    assert_empty result
  end

  def test_all_instance_paths_orders_nested_shared_instances_from_root
    root = Object.new
    outer = Sketchup::ComponentDefinition.new('Outer')
    middle = Sketchup::ComponentDefinition.new('Middle')
    leaf = Sketchup::ComponentDefinition.new('Leaf')
    first = add_instance(outer, root)
    second = add_instance(outer, root)
    nested = add_instance(middle, outer)
    target = add_instance(leaf, middle)

    assert_equal [[first, nested, target], [second, nested, target]],
                 SupexStdlib::ComponentDefinition.all_instance_paths(leaf)
  end

  def test_all_instance_paths_excludes_unused_parent_definitions
    root = Object.new
    unused = Sketchup::ComponentDefinition.new('Unused')
    leaf = Sketchup::ComponentDefinition.new('Leaf')
    add_instance(leaf, unused)
    reachable = add_instance(leaf, root)

    assert_equal [[reachable]], SupexStdlib::ComponentDefinition.all_instance_paths(leaf)
  end

  private

  def add_instance(definition, parent)
    instance = Sketchup::ComponentInstance.new
    instance.definition = definition
    instance.parent = parent
    definition.instances << instance
    instance
  end
end
