# frozen_string_literal: true

# SketchUp unit conversion extensions on Numeric.
# SketchUp internal units are inches.
# .mm converts mm -> inches, .to_mm converts inches -> mm.
class Numeric
  def mm
    self / 25.4
  end

  def to_mm
    self * 25.4
  end
end
