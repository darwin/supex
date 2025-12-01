# frozen_string_literal: true

# =============================================================================
# SketchUp API Mocks for Testing
# =============================================================================

# Mock geometry classes
class MockPoint
  attr_accessor :x, :y, :z

  def initialize(x = 0, y = 0, z = 0)
    @x = x
    @y = y
    @z = z
  end

  def to_a
    [x, y, z]
  end
end

class MockVector
  attr_accessor :x, :y, :z

  def initialize(x = 0, y = 0, z = 0)
    @x = x
    @y = y
    @z = z
  end

  def to_a
    [x, y, z]
  end
end

class MockBounds
  attr_accessor :min, :max, :center

  def initialize(min: MockPoint.new(0, 0, 0), max: MockPoint.new(10, 10, 10))
    @min = min
    @max = max
    @center = MockPoint.new(
      (min.x + max.x) / 2.0,
      (min.y + max.y) / 2.0,
      (min.z + max.z) / 2.0
    )
  end
end

class MockColor
  attr_accessor :red, :green, :blue

  def initialize(r: 255, g: 255, b: 255)
    @red = r
    @green = g
    @blue = b
  end
end

# Mock SketchUp entity classes
module Sketchup
  class Entity
    attr_accessor :entityID, :layer, :valid

    def initialize(id: rand(10_000))
      @entityID = id
      @layer = MockLayer.new
      @valid = true
    end

    def typename
      self.class.name.split('::').last
    end

    def valid?
      @valid
    end
  end

  class Face < Entity
    attr_accessor :area, :normal, :bounds

    def initialize(id: rand(10_000), area: 100.0)
      super(id: id)
      @area = area
      @normal = MockVector.new(0, 0, 1)
      @bounds = MockBounds.new
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end
  end

  class Edge < Entity
    attr_accessor :length, :bounds

    def initialize(id: rand(10_000), length: 10.0)
      super(id: id)
      @length = length
      @bounds = MockBounds.new
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end
  end

  class Group < Entity
    attr_accessor :name, :bounds

    def initialize(id: rand(10_000), name: '')
      super(id: id)
      @name = name
      @bounds = MockBounds.new
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end
  end

  class ComponentInstance < Entity
    attr_accessor :definition, :bounds

    def initialize(id: rand(10_000), definition_name: 'Component')
      super(id: id)
      @definition = MockComponentDefinition.new(definition_name)
      @bounds = MockBounds.new
    end

    def respond_to?(method, include_private = false)
      method == :bounds || super
    end
  end
end

class MockComponentDefinition
  attr_reader :name

  def initialize(name)
    @name = name
  end
end

# Mock layer
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

# Mock collections
class MockEntities
  include Enumerable

  def initialize
    @entities = []
  end

  def each(&block)
    @entities.each(&block)
  end

  def add_entity(entity)
    @entities << entity
    entity
  end

  def grep(type)
    @entities.select { |e| e.is_a?(type) }
  end

  def map(&block)
    @entities.map(&block)
  end

  def to_a
    @entities.dup
  end

  def count
    @entities.length
  end

  def find_by_id(id)
    @entities.find { |e| e.entityID == id }
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

  def map(&block)
    @layers.map(&block)
  end

  def add_layer(layer)
    @layers << layer
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

  def map(&block)
    @materials.map(&block)
  end

  def add_material(material)
    @materials << material
  end
end

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

  def map(&block)
    @selection.map(&block)
  end

  def add(entity)
    @selection << entity
  end

  def clear
    @selection.clear
  end
end

class MockCamera
  attr_accessor :eye, :target, :up, :fov, :aspect_ratio

  def initialize
    @eye = MockPoint.new(0, 0, 100)
    @target = MockPoint.new(0, 0, 0)
    @up = MockVector.new(0, 1, 0)
    @fov = 45.0
    @aspect_ratio = 1.777
  end

  def perspective?
    true
  end
end

class MockView
  attr_accessor :camera

  def initialize
    @camera = MockCamera.new
  end

  def write_image(options)
    FileUtils.touch(options[:filename]) if options[:filename]
    true
  end
end

class MockModel
  attr_accessor :title, :path, :entities, :selection, :layers, :materials, :active_view, :options

  def initialize(path: nil, title: 'Untitled')
    @path = path
    @title = title
    @entities = MockEntities.new
    @selection = MockSelection.new
    @layers = MockLayers.new
    @materials = MockMaterials.new
    @active_view = MockView.new
    @options = { 'UnitsOptions' => { 'LengthUnit' => 2 } }
  end

  def modified?
    false
  end

  def find_entity_by_id(id)
    @entities.find_by_id(id)
  end

  def save(path = nil)
    @path = path if path
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
end

# Mock Sketchup module singleton methods
module Sketchup
  @mock_model = nil
  @mock_version = '2026.0.0'

  class << self
    attr_accessor :mock_model, :mock_version

    def active_model
      @mock_model ||= MockModel.new
    end

    def version
      @mock_version
    end

    def send_action(_action)
      true
    end

    def open_file(path)
      @mock_model = MockModel.new(path: path)
      true
    end

    def reset_mocks
      @mock_model = nil
    end
  end
end

# Mock SKETCHUP_CONSOLE
SKETCHUP_CONSOLE = Object.new
class << SKETCHUP_CONSOLE
  attr_accessor :shown

  def show
    @shown = true
  end
end

# Mock menu for UI.menu
class MockMenu
  attr_reader :name, :items, :submenus

  def initialize(name)
    @name = name
    @items = []
    @submenus = {}
  end

  def add_item(label, &block)
    @items << { label: label, block: block }
    @items.length - 1
  end

  def add_separator
    @items << { separator: true }
  end

  def add_submenu(name)
    @submenus[name] ||= MockMenu.new(name)
  end
end

# Mock UI module (SketchUp API)
# Constants for messagebox
MB_OK = 0
MB_OKCANCEL = 1
MB_YESNO = 4
MB_YESNOCANCEL = 3

module UI
  @timers = {}
  @timer_id = 0
  @messageboxes = []
  @menus = {}

  class << self
    attr_accessor :messageboxes, :menus

    def start_timer(interval, repeat, &block)
      @timer_id += 1
      @timers[@timer_id] = { interval: interval, repeat: repeat, block: block }
      @timer_id
    end

    def stop_timer(id)
      @timers.delete(id)
    end

    def clear_timers
      @timers.clear
      @timer_id = 0
    end

    def timers
      @timers
    end

    def messagebox(message, type = MB_OK)
      @messageboxes ||= []
      @messageboxes << { message: message, type: type }
      1 # Return OK
    end

    def menu(name)
      @menus ||= {}
      @menus[name] ||= MockMenu.new(name)
    end

    def reset_ui_mocks
      @messageboxes = []
      @menus = {}
    end
  end
end
