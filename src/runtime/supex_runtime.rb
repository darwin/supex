# frozen_string_literal: true

require 'sketchup'
require 'extensions'

# Load version information from sources
require 'version'

module SupexRuntime
  unless file_loaded?(__FILE__)
    ex = SketchupExtension.new('Supex Runtime', 'main')
    ex.description = 'Modern SketchUp Model Context Protocol server for AI-driven 3D automation'
    ex.version     = SupexRuntime::VERSION
    ex.copyright   = '2024 Antonin'
    ex.creator     = 'Antonin'

    # Set required SketchUp version (if method exists)
    if ex.respond_to?(:required_sketchup_version=)
      ex.required_sketchup_version = SupexRuntime::REQUIRED_SKETCHUP_VERSION.to_i
    end

    Sketchup.register_extension(ex, true)
    file_loaded(__FILE__)
  end
end
