# frozen_string_literal: true

module SketchupMock
  class MockModel
    attr_accessor :title, :path, :selection, :layers, :materials,
                  :active_view, :options, :bounds, :active_path, :definitions

    def initialize(path: nil, title: 'Untitled')
      @path = path
      @title = title
      @entities = MockEntities.new(self)
      @definitions = MockDefinitionList.new
      @selection = MockSelection.new
      @layers = MockLayers.new
      @materials = MockMaterials.new
      @active_view = MockView.new
      @options = { 'UnitsOptions' => { 'LengthUnit' => 2 } }
      @bounds = Geom::BoundingBox.new
      @active_path = nil
      @rendering_options = MockRenderingOptions.new
    end

    attr_reader :entities, :rendering_options

    def active_entities
      @entities
    end

    def modified?
      false
    end

    def find_entity_by_id(id)
      SketchupMock::EntityRegistry.find(id)
    end

    def save(path = nil)
      @path = path if path
      true
    end

    def export(_path, _options = {})
      true
    end

    def start_operation(_name, _disable_ui = false)
      true
    end

    def commit_operation
      true
    end

    def abort_operation
      true
    end

    def reset
      @entities = MockEntities.new(self)
      @definitions = MockDefinitionList.new
      @selection = MockSelection.new
      @layers.reset
      @materials.reset
      @active_view = MockView.new
      @bounds = Geom::BoundingBox.new
      @active_path = nil
      @title = 'Untitled'
      @path = nil
    end
  end
end
