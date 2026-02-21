# frozen_string_literal: true

module SketchupMock
  class MockLayer
    attr_accessor :name, :visible, :page_behavior

    def initialize(name: 'Layer0', visible: true)
      @name = name
      @visible = visible
      @page_behavior = 0
    end

    def visible?
      @visible
    end
  end

  class MockLayers
    include Enumerable

    def initialize
      @layers = [MockLayer.new]
    end

    def each(&block)
      @layers.each(&block)
    end

    def add(name)
      layer = MockLayer.new(name: name)
      @layers << layer
      layer
    end

    def [](name)
      @layers.find { |l| l.name == name }
    end

    def reset
      @layers = [MockLayer.new]
    end
  end

  # Default layer singleton for new entities
  def self.default_layer
    @default_layer ||= MockLayer.new
  end

  def self.reset_default_layer
    @default_layer = MockLayer.new
  end
end
