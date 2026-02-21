# frozen_string_literal: true

module SketchupMock
  class MockSelection
    include Enumerable

    def initialize
      @selection = []
    end

    def each(&block)
      @selection.each(&block)
    end

    def count
      @selection.length
    end

    def add(entity)
      @selection << entity
    end

    def remove(entity)
      @selection.delete(entity)
    end

    def clear
      @selection.clear
    end

    def empty?
      @selection.empty?
    end

    def reset
      @selection.clear
    end
  end
end
