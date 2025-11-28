# frozen_string_literal: true

require 'sketchup'
require 'extensions'

# Load version information from sources
require_relative 'supex_runtime/version'

module SupexRuntime
  unless file_loaded?(__FILE__)
    ex = SketchupExtension.new(SupexRuntime::EXTENSION_NAME, 'main')
    ex.description = SupexRuntime::EXTENSION_DESCRIPTION
    ex.version     = SupexRuntime::VERSION
    ex.copyright   = SupexRuntime::EXTENSION_COPYRIGHT
    ex.creator     = SupexRuntime::EXTENSION_CREATOR

    # Set required SketchUp version (if method exists)
    if ex.respond_to?(:required_sketchup_version=)
      # noinspection RubyResolve
      ex.required_sketchup_version = SupexRuntime::REQUIRED_SKETCHUP_VERSION.to_i
    end

    Sketchup.register_extension(ex, true)
    file_loaded(__FILE__)
  end
end
