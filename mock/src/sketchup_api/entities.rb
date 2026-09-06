# frozen_string_literal: true

module SketchupMock
  # MockEntities collection that tracks its owner (Model or ComponentDefinition).
  # Provides add_instance, grep, clear!, manifold? and Enumerable.
  class MockEntities
    include Enumerable

    attr_reader :owner

    def initialize(owner = nil)
      @entities = []
      @owner = owner
      @manifold = true
    end

    def each(&)
      @entities.each(&)
    end

    def add_entity(entity)
      @entities << entity
      entity
    end

    def add_instance(definition, transformation = nil)
      instance = Sketchup::ComponentInstance.new(definition, transformation)
      instance.parent = MockEntityParent.new(self)
      definition.instances << instance
      @entities << instance
      instance
    end

    def add_face(*_args)
      face = Sketchup::Face.new
      @entities << face
      face
    end

    def add_edge(*_args)
      edge = Sketchup::Edge.new
      @entities << edge
      edge
    end

    def add_group
      group = Sketchup::Group.new
      group.parent = MockEntityParent.new(self)
      @entities << group
      group
    end

    def grep(type)
      @entities.grep(type)
    end

    def to_a
      @entities.dup
    end

    def count
      @entities.length
    end

    def length
      @entities.length
    end

    def empty?
      @entities.empty?
    end

    def clear!
      @entities.each do |e|
        e.invalidate! if e.respond_to?(:invalidate!)
      end
      @entities.clear
    end

    def remove_entity(entity)
      @entities.delete(entity)
    end

    def find_by_id(id)
      @entities.find { |e| e.entityID == id.to_i }
    end

    # Configurable manifold? for testing
    def manifold?
      @manifold
    end

    def set_manifold(value)
      @manifold = value
    end
  end

  # Wrapper providing .entities accessor for parent chain (inst.parent.entities).
  class MockEntityParent
    attr_reader :entities

    def initialize(entities)
      @entities = entities
    end

    def respond_to?(method, include_private = false)
      method == :entities || super
    end
  end
end
