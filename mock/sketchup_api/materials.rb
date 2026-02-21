# frozen_string_literal: true

module SketchupMock
  class MockColor
    attr_accessor :red, :green, :blue

    def initialize(r: 255, g: 255, b: 255)
      @red = r
      @green = g
      @blue = b
    end
  end

  class MockMaterial
    attr_accessor :name, :display_name, :color, :alpha, :texture

    def initialize(name: 'Material1')
      @name = name
      @display_name = name
      @color = MockColor.new
      @alpha = 1.0
      @texture = nil
    end
  end

  class MockMaterials
    include Enumerable

    def initialize
      @materials = []
    end

    def each(&block)
      @materials.each(&block)
    end

    def add(name)
      mat = MockMaterial.new(name: name)
      @materials << mat
      mat
    end

    def [](name)
      @materials.find { |m| m.name == name }
    end

    def reset
      @materials.clear
    end
  end
end
