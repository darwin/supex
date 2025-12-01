# frozen_string_literal: true

# Extensions to SketchUp classes for better REPL experience
# Provides chainable methods for common operations

class Sketchup::Group
  # Moves group to XY position (chainable)
  #
  # @param x [Length] X position
  # @param y [Length] Y position
  # @return [self] For chaining
  def move_to(x, y)
    vector = Geom::Vector3d.new(x, y, 0)
    transform!(Geom::Transformation.new(vector))
    self
  end
end
