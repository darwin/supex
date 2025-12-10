# frozen_string_literal: true

require_relative 'test_helper'

class EntityTest < Minitest::Test
  # instance? tests

  def test_instance_group
    group = Sketchup::Group.new

    assert SupexStdlib::Entity.instance?(group)
  end

  def test_instance_component_instance
    instance = Sketchup::ComponentInstance.new

    assert SupexStdlib::Entity.instance?(instance)
  end

  def test_instance_other_entity
    entity = Sketchup::Entity.new

    refute SupexStdlib::Entity.instance?(entity)
  end

  # definition tests

  def test_definition_component_instance
    definition = Sketchup::ComponentDefinition.new('TestDef')
    instance = Sketchup::ComponentInstance.new
    instance.definition = definition

    result = SupexStdlib::Entity.definition(instance)

    assert_equal definition, result
  end

  def test_definition_group
    definition = Sketchup::ComponentDefinition.new('GroupDef')
    group = Sketchup::Group.new
    group.definition = definition

    result = SupexStdlib::Entity.definition(group)

    assert_equal definition, result
  end

  # copy_attributes tests

  def test_copy_attributes_empty_source
    source = Sketchup::Entity.new
    target = Sketchup::Entity.new

    SupexStdlib::Entity.copy_attributes(target, source)

    assert_nil target.attribute_dictionaries
  end

  def test_copy_attributes_with_data
    source = Sketchup::Entity.new
    source.set_attribute('my_dict', 'key1', 'value1')
    source.set_attribute('my_dict', 'key2', 42)

    target = Sketchup::Entity.new
    SupexStdlib::Entity.copy_attributes(target, source)

    assert_equal 'value1', target.get_attribute('my_dict', 'key1')
    assert_equal 42, target.get_attribute('my_dict', 'key2')
  end

  def test_copy_attributes_skips_credits
    source = Sketchup::Entity.new
    source.set_attribute('GSU_ContributorsInfo', 'author', 'Someone')
    source.set_attribute('my_dict', 'data', 'test')

    target = Sketchup::Entity.new
    SupexStdlib::Entity.copy_attributes(target, source)

    assert_equal 'test', target.get_attribute('my_dict', 'data')
    assert_nil target.get_attribute('GSU_ContributorsInfo', 'author')
  end

  def test_copy_attributes_multiple_dicts
    source = Sketchup::Entity.new
    source.set_attribute('dict1', 'key1', 'value1')
    source.set_attribute('dict2', 'key2', 'value2')

    target = Sketchup::Entity.new
    SupexStdlib::Entity.copy_attributes(target, source)

    assert_equal 'value1', target.get_attribute('dict1', 'key1')
    assert_equal 'value2', target.get_attribute('dict2', 'key2')
  end

  # get_attribute / set_attribute tests

  def test_get_attribute_returns_value
    entity = Sketchup::Entity.new
    entity.set_attribute('dict', 'key', 'value')

    result = SupexStdlib::Entity.get_attribute(entity, 'dict', 'key')

    assert_equal 'value', result
  end

  def test_get_attribute_returns_default_when_missing
    entity = Sketchup::Entity.new

    result = SupexStdlib::Entity.get_attribute(entity, 'dict', 'key', 'default')

    assert_equal 'default', result
  end

  def test_set_attribute_creates_attribute
    entity = Sketchup::Entity.new

    SupexStdlib::Entity.set_attribute(entity, 'dict', 'key', 'value')

    assert_equal 'value', entity.get_attribute('dict', 'key')
  end

  # has_dictionary? tests

  def test_has_dictionary_returns_true
    entity = Sketchup::Entity.new
    entity.set_attribute('my_dict', 'key', 'value')

    assert SupexStdlib::Entity.has_dictionary?(entity, 'my_dict')
  end

  def test_has_dictionary_returns_false
    entity = Sketchup::Entity.new

    refute SupexStdlib::Entity.has_dictionary?(entity, 'my_dict')
  end

  # dictionary_names tests

  def test_dictionary_names_returns_all_names
    entity = Sketchup::Entity.new
    entity.set_attribute('dict1', 'key', 'value')
    entity.set_attribute('dict2', 'key', 'value')

    names = SupexStdlib::Entity.dictionary_names(entity)

    assert_includes names, 'dict1'
    assert_includes names, 'dict2'
  end

  def test_dictionary_names_returns_empty_when_none
    entity = Sketchup::Entity.new

    names = SupexStdlib::Entity.dictionary_names(entity)

    assert_empty names
  end

  # Module structure tests

  def test_module_exists
    assert defined?(SupexStdlib::Entity)
  end

  def test_credits_constant_defined
    assert_equal 'GSU_ContributorsInfo', SupexStdlib::Entity::CREDITS_DICT
  end

  def test_responds_to_definition
    assert_respond_to SupexStdlib::Entity, :definition
  end

  def test_responds_to_instance?
    assert_respond_to SupexStdlib::Entity, :instance?
  end

  def test_responds_to_swap_definition
    assert_respond_to SupexStdlib::Entity, :swap_definition
  end

  def test_responds_to_copy_attributes
    assert_respond_to SupexStdlib::Entity, :copy_attributes
  end

  def test_responds_to_get_attribute
    assert_respond_to SupexStdlib::Entity, :get_attribute
  end

  def test_responds_to_set_attribute
    assert_respond_to SupexStdlib::Entity, :set_attribute
  end

  def test_responds_to_has_dictionary?
    assert_respond_to SupexStdlib::Entity, :has_dictionary?
  end

  def test_responds_to_dictionary_names
    assert_respond_to SupexStdlib::Entity, :dictionary_names
  end
end
