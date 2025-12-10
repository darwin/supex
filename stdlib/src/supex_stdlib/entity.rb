# frozen_string_literal: true

# Entity utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  # Utilities for working with SketchUp entities.
  #
  # Provides helper methods for instances (Groups and ComponentInstances),
  # attribute manipulation, and entity inspection.
  module Entity
    extend self

    # Attribute dictionary name for SketchUp's component credits (read-only).
    CREDITS_DICT = 'GSU_ContributorsInfo'

    # Get the definition used by an instance.
    #
    # @param instance [Sketchup::ComponentInstance, Sketchup::Group, Sketchup::Image]
    # @return [Sketchup::ComponentDefinition]
    #
    # @example
    #   definition = SupexStdlib::Entity.definition(group)
    def definition(instance)
      instance.definition
    end

    # Test if entity is either a Group or ComponentInstance.
    #
    # Since a group is a special type of component, groups and component
    # instances can often be treated the same way.
    #
    # @param entity [Sketchup::Entity]
    # @return [Boolean]
    #
    # @example
    #   if SupexStdlib::Entity.instance?(entity)
    #     puts entity.transformation
    #   end
    def instance?(entity)
      entity.is_a?(Sketchup::Group) || entity.is_a?(Sketchup::ComponentInstance)
    end

    # Swap the definition used by an instance.
    #
    # As SketchUp doesn't support swapping group definitions or swap between
    # a group definition and a component definition, a new instance is
    # created in these cases.
    #
    # @param instance [Sketchup::ComponentInstance, Sketchup::Group]
    # @param new_definition [Sketchup::ComponentDefinition]
    # @return [Sketchup::ComponentInstance, Sketchup::Group] the resulting instance
    #
    # @example
    #   new_instance = SupexStdlib::Entity.swap_definition(group, component_def)
    def swap_definition(instance, new_definition)
      if instance.is_a?(Sketchup::Group) || new_definition.group?
        old_instance = instance
        instance = old_instance.parent.entities.add_instance(
          new_definition,
          old_instance.transformation
        )
        instance.material = old_instance.material
        instance.layer = old_instance.layer
        instance.hidden = old_instance.hidden?
        copy_attributes(instance, old_instance)
        old_instance.erase!
      else
        instance.definition = new_definition
      end

      instance
    end

    # Copy all attributes from a source entity to a target entity.
    #
    # Skips SketchUp's read-only GSU_ContributorsInfo dictionary.
    #
    # @param target [Sketchup::Entity] entity to copy attributes to
    # @param source [Sketchup::Entity] entity to copy attributes from
    # @return [nil]
    #
    # @note Entity#attribute_dictionaries returns nil instead of empty
    #   Array when empty.
    #
    # @example
    #   SupexStdlib::Entity.copy_attributes(new_instance, old_instance)
    def copy_attributes(target, source)
      dicts = source.attribute_dictionaries || []

      dicts.each do |dict|
        next if dict.name == CREDITS_DICT

        dict.each_pair do |key, value|
          target.set_attribute(dict.name, key, value)
        end
      end

      nil
    end

    # Get a specific attribute from an entity.
    #
    # @param entity [Sketchup::Entity]
    # @param dict_name [String] dictionary name
    # @param key [String] attribute key
    # @param default [Object] default value if not found
    # @return [Object] attribute value or default
    def get_attribute(entity, dict_name, key, default = nil)
      entity.get_attribute(dict_name, key, default)
    end

    # Set a specific attribute on an entity.
    #
    # @param entity [Sketchup::Entity]
    # @param dict_name [String] dictionary name
    # @param key [String] attribute key
    # @param value [Object] value to set
    # @return [Object] the value that was set
    def set_attribute(entity, dict_name, key, value)
      entity.set_attribute(dict_name, key, value)
    end

    # Check if an entity has a specific attribute dictionary.
    #
    # @param entity [Sketchup::Entity]
    # @param dict_name [String] dictionary name
    # @return [Boolean]
    def has_dictionary?(entity, dict_name)
      dicts = entity.attribute_dictionaries
      return false if dicts.nil?

      dicts.any? { |dict| dict.name == dict_name }
    end

    # Get all dictionary names from an entity.
    #
    # @param entity [Sketchup::Entity]
    # @return [Array<String>] list of dictionary names
    def dictionary_names(entity)
      dicts = entity.attribute_dictionaries
      return [] if dicts.nil?

      dicts.map(&:name)
    end
  end
end
