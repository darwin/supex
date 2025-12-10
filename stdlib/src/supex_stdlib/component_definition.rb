# frozen_string_literal: true

# ComponentDefinition utilities adapted from sketchup-community-lib (MIT License).
# https://github.com/Eneroth3/sketchup-community-lib

module SupexStdlib
  # Utilities for working with Sketchup::ComponentDefinition entities.
  module ComponentDefinition
    extend self

    # Erase a definition from the model.
    #
    # Removes all instances and clears the definition's entities.
    #
    # @param definition [Sketchup::ComponentDefinition]
    # @return [nil]
    #
    # @note This method must run inside of an operation (Model#start_operation).
    #   Otherwise the component will not be erased and SketchUp may crash.
    #
    # @example
    #   model.start_operation('Erase Definition', true)
    #   SupexStdlib::ComponentDefinition.erase(definition)
    #   model.commit_operation
    def erase(definition)
      definition.instances.each(&:erase!)

      # Erasing all entities purges the definition from the model.
      # Must be done within an operation for safety.
      definition.entities.clear!

      nil
    end

    # Define new axes placement for a component.
    #
    # Transforms all entities in the definition and optionally adjusts
    # instance transformations to keep geometry in place.
    #
    # @param definition [Sketchup::ComponentDefinition]
    # @param new_axes [Geom::Transformation] new axes relative to current axes
    # @param adjust_instances [Boolean] whether to adjust instance transformations
    # @return [nil]
    #
    # @example Move axes to bounding box bottom center
    #   bb = definition.bounds
    #   bottom_center = Geom.linear_combination(0.5, bb.corner(0), 0.5, bb.corner(3))
    #   new_axes = Geom::Transformation.new(bottom_center)
    #   SupexStdlib::ComponentDefinition.place_axes(definition, new_axes)
    def place_axes(definition, new_axes, adjust_instances = true)
      definition.entities.transform_entities(
        new_axes.inverse,
        definition.entities.to_a
      )

      if adjust_instances
        definition.instances.each do |instance|
          instance.transformation *= new_axes
        end
      end

      nil
    end

    # Check if a definition is only used within certain scopes.
    #
    # Returns true if all instances of the definition are contained within
    # the specified scopes (definitions, instances, or instance paths).
    #
    # @param definition [Sketchup::ComponentDefinition]
    # @param scopes [Sketchup::ComponentDefinition, Sketchup::ComponentInstance,
    #                Sketchup::Group, Array] scope(s) to check
    # @return [Boolean]
    #
    # @example Check if definition is unique to selection
    #   unique = SupexStdlib::ComponentDefinition.unique_to?(definition, model.selection.to_a)
    def unique_to?(definition, scopes)
      raise ArgumentError, 'Expected ComponentDefinition.' unless definition.is_a?(Sketchup::ComponentDefinition)

      scopes = [scopes] unless scopes.is_a?(Array)
      raise ArgumentError, 'Scope is empty.' if scopes.empty?

      # Get all instance paths for this definition
      all_paths = all_instance_paths(definition)

      all_paths.all? do |path|
        scopes.any? { |scope| instance_path_matches_scope?(path, scope) }
      end
    end

    # Get all instance paths for a definition.
    #
    # Returns an array of arrays, where each inner array represents
    # the path of instances from root to the definition's instances.
    #
    # @param definition [Sketchup::ComponentDefinition]
    # @return [Array<Array<Sketchup::Entity>>]
    def all_instance_paths(definition)
      paths = []

      definition.instances.each do |instance|
        collect_paths_to_instance(instance, [], paths)
      end

      paths
    end

    private

    # Recursively collect all paths to an instance.
    def collect_paths_to_instance(instance, current_path, paths)
      new_path = current_path + [instance]

      parent = instance.parent
      if parent.is_a?(Sketchup::ComponentDefinition)
        if parent.instances.empty?
          # Definition is in model root
          paths << new_path
        else
          parent.instances.each do |parent_instance|
            collect_paths_to_instance(parent_instance, new_path, paths)
          end
        end
      else
        # Parent is model entities
        paths << new_path
      end
    end

    # Check if an instance path matches a scope.
    def instance_path_matches_scope?(path, scope)
      case scope
      when Sketchup::ComponentDefinition
        path.any? do |instance|
          Entity.instance?(instance) && Entity.definition(instance) == scope
        end
      when Sketchup::ComponentInstance, Sketchup::Group
        path.include?(scope)
      when Sketchup::InstancePath
        path.take(scope.size) == scope.to_a
      else
        raise ArgumentError, "Unexpected scope #{scope.class}."
      end
    end
  end
end
