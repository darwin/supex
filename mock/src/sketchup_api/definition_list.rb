# frozen_string_literal: true

module SketchupMock
  # MockDefinitionList with mesh import.
  # Parses mesh file minimally (vertex positions + face indices) for BoundingBox computation.
  class MockDefinitionList
    include Enumerable

    def initialize
      @definitions = []
    end

    def each(&)
      @definitions.each(&)
    end

    def select(&)
      @definitions.select(&)
    end

    def find(&)
      @definitions.find(&)
    end

    def to_a
      @definitions.dup
    end

    def count
      @definitions.length
    end

    def length
      @definitions.length
    end

    # SketchUp 2026: import returns ComponentDefinition directly.
    # Minimal mesh parsing for vertex positions and face indices.
    def import(mesh_path)
      raise "File not found: #{mesh_path}" unless File.exist?(mesh_path)

      defn = Sketchup::ComponentDefinition.new("imported_#{@definitions.length}")
      parse_mesh_into_definition(defn, mesh_path)
      @definitions << defn
      defn
    end

    def add(name_or_defn)
      if name_or_defn.is_a?(Sketchup::ComponentDefinition)
        @definitions << name_or_defn
        name_or_defn
      else
        defn = Sketchup::ComponentDefinition.new(name_or_defn)
        @definitions << defn
        defn
      end
    end

    def remove(defn)
      @definitions.delete(defn)
    end

    def [](name)
      @definitions.find { |d| d.name == name }
    end

    def reset
      @definitions.clear
    end

    private

    def parse_mesh_into_definition(defn, mesh_path)
      vertices = []
      faces = []

      File.readlines(mesh_path).each do |line|
        parts = line.strip.split
        next if parts.empty?

        case parts[0]
        when 'v'
          # Vertex: v x y z
          next unless parts.length >= 4

          vertices << Geom::Point3d.new(parts[1].to_f, parts[2].to_f, parts[3].to_f)
        when 'f'
          # Face: f v1 v2 v3 ... (indices may have /vt/vn format)
          indices = parts[1..].map { |p| p.split('/')[0].to_i }
          faces << indices
        end
      end

      # Compute bounding box from vertices
      vertices.each { |v| defn.bounds.add(v) }

      # Store mesh data on the definition for later retrieval
      defn.set_attribute('_mock', 'vertices', vertices.map(&:to_a))
      defn.set_attribute('_mock', 'faces', faces)
      defn.set_attribute('_mock', 'mesh_path', mesh_path)
    end
  end
end
