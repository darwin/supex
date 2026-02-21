# frozen_string_literal: true

module Sketchup
  class ComponentInstance < Entity
    attr_accessor :definition, :transformation, :material, :name

    def initialize(definition, transformation = nil)
      super()
      @definition = definition
      @transformation = transformation || Geom::Transformation.new
      @material = nil
      @name = ''
      @parent_ref = nil
    end

    def bounds
      @definition.bounds
    end

    def parent
      @parent_ref
    end

    def parent=(p)
      @parent_ref = p
    end

    def erase!
      @definition.instances.delete(self)
      @parent_ref&.entities&.remove_entity(self) if @parent_ref.respond_to?(:entities)
      invalidate!
    end

    def respond_to?(method, include_private = false)
      %i[bounds layer material name name=].include?(method) || super
    end
  end
end
