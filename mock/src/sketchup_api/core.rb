# frozen_string_literal: true

# SketchUp API mock core — loads all sub-modules and sets up the Sketchup module singleton.
# This file should be required before loading any real supex runtime code.

require 'fileutils'
require 'json'

# Load mock infrastructure
require_relative 'entity_registry'
require_relative 'attribute_dictionary'
require_relative 'geometry'
require_relative 'transformation'
require_relative 'units'
require_relative 'layers'
require_relative 'materials'
require_relative 'camera'
require_relative 'selection'
require_relative 'polygon_mesh'

# Entity types (depend on infrastructure above)
require_relative 'component_definition'
require_relative 'component_instance'
require_relative 'face'

# Collections (depend on entity types)
require_relative 'entities'
require_relative 'definition_list'
require_relative 'model'

# UI module
require_relative 'ui'

# Mock SKETCHUP_CONSOLE
SKETCHUP_CONSOLE = Object.new
class << SKETCHUP_CONSOLE
  attr_accessor :shown

  def show
    @shown = true
  end
end

# Sketchup module singleton methods
module Sketchup
  @mock_model = nil
  @mock_version = '2026.0.0'
  @force_no_model = false

  class << self
    attr_accessor :mock_model, :mock_version, :force_no_model

    def active_model
      return nil if @force_no_model

      @mock_model ||= SketchupMock::MockModel.new
    end

    def version
      @mock_version
    end

    def send_action(_action)
      true
    end

    def open_file(path)
      @mock_model = SketchupMock::MockModel.new(path: path, title: File.basename(path, '.*'))
      true
    end

    def register_extension(_ext, _load = true)
      true
    end

    def reset_mocks
      @mock_model = nil
      @force_no_model = false
      SketchupMock::EntityRegistry.reset
      SketchupMock.reset_default_layer
    end
  end
end

# Stub for SketchupExtension (used by supex_runtime.rb entry point, not loaded in mock)
class SketchupExtension
  attr_accessor :name, :version, :description, :creator, :copyright

  def initialize(name, path)
    @name = name
    @path = path
  end
end

# Stubs for file_loaded tracking (SketchUp extension guard)
def file_loaded?(_path)
  false
end

def file_loaded(_path)
  true
end
