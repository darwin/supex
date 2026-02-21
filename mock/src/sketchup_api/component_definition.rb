# frozen_string_literal: true

module Sketchup
  class Entity
    include SketchupMock::AttributeDictionary

    attr_reader :entityID
    attr_accessor :layer

    def initialize
      @entityID = SketchupMock::EntityRegistry.next_id
      @layer = SketchupMock.default_layer
      @valid = true
      @attribute_dictionaries = {}
      SketchupMock::EntityRegistry.register(self)
    end

    def typename
      self.class.name.split('::').last
    end

    def valid?
      @valid
    end

    def deleted?
      !@valid
    end

    def invalidate!
      @valid = false
    end

    def respond_to?(method, include_private = false)
      super
    end
  end

  class ComponentDefinition < Entity
    attr_accessor :name, :bounds
    attr_reader :instances, :entities

    def initialize(name = 'Component')
      super()
      @name = name
      @entities = SketchupMock::MockEntities.new(self)
      @instances = []
      @bounds = Geom::BoundingBox.new
    end

    def is_a?(klass)
      return true if klass == Sketchup::ComponentDefinition

      super
    end
  end
end
