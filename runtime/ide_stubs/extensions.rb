# frozen_string_literal: true

# IDE shim for SketchUp extensions module
# This file allows IntelliJ to resolve `require 'extensions'`
# In actual SketchUp runtime, this module is built-in.

require 'sketchup-api-stubs'
