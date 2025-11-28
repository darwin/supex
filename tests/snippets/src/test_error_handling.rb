# Ruby snippets for test_error_handling.py
# Functions that intentionally raise errors for testing error handling
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts

require 'json'

module SupexTestSnippets
  # Intentionally raises a runtime error.
  # @return [never] Raises RuntimeError with message "Intentional test error"
  def self.error_raise_runtime
    raise "Intentional test error"
  end

  # Attempts an invalid SketchUp API call (nil argument).
  # @return [never] Raises ArgumentError from SketchUp API
  def self.error_invalid_api_call
    Sketchup.active_model.entities.add_face(nil)
  end

  # Causes integer division by zero.
  # @return [never] Raises ZeroDivisionError
  def self.error_division_by_zero
    1 / 0
  end

  # Accesses undefined variable.
  # @return [never] Raises NameError
  def self.error_undefined_variable
    undefined_variable_xyz
  end

  # Calls method on nil.
  # @return [never] Raises NoMethodError
  def self.error_nil_method_call
    nil.some_method_that_does_not_exist
  end
end
