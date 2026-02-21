# frozen_string_literal: true

# Auto-incrementing entity ID registry with global lookup.
# Deterministic IDs (starting from 1) for test reproducibility.
module SketchupMock
  module EntityRegistry
    @next_id = 1
    @entities = {}

    class << self
      def next_id
        id = @next_id
        @next_id += 1
        id
      end

      def register(entity)
        @entities[entity.entityID] = entity
      end

      def find(id)
        @entities[id.to_i]
      end

      def all
        @entities.values
      end

      def reset
        @next_id = 1
        @entities.clear
      end
    end
  end
end
