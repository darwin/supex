# frozen_string_literal: true

require_relative 'supex_stdlib/platform'
require_relative 'supex_stdlib/shell'
require_relative 'supex_stdlib/geom'
require_relative 'supex_stdlib/entity'
require_relative 'supex_stdlib/face'
require_relative 'supex_stdlib/edge'
require_relative 'supex_stdlib/component_definition'
require_relative 'supex_stdlib/color'

# Supex Standard Library
# Provides utility functions for SketchUp model introspection and manipulation.
# This module is loaded automatically when SupexRuntime starts.
module SupexStdlib
  VERSION = '0.2.0'
  LOADED = true
end
