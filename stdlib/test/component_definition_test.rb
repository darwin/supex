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
end
