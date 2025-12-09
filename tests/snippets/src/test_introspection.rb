# frozen_string_literal: true

# Ruby snippets for test_introspection.py
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts
# All functions return JSON strings for structured assertions

require 'json'

module SupexTestSnippets
  # Adds a 1m x 1m face at origin on XY plane.
  # @return [String] JSON: {"faces": 1, "edges": 4}
  def self.geom_add_face
    model = Sketchup.active_model
    model.start_operation('Add Geometry', true)
    model.entities.add_face([0, 0, 0], [1.m, 0, 0], [1.m, 1.m, 0], [0, 1.m, 0])
    model.commit_operation
    {
      faces: model.entities.grep(Sketchup::Face).length,
      edges: model.entities.grep(Sketchup::Edge).length
    }.to_json
  end

  # Adds two connected edges forming an L shape.
  # @return [String] JSON: {"edges": 2}
  def self.geom_add_edges
    model = Sketchup.active_model
    model.start_operation('Add Edges', true)
    model.entities.add_line([0, 0, 0], [1.m, 0, 0])
    model.entities.add_line([1.m, 0, 0], [1.m, 1.m, 0])
    model.commit_operation
    { edges: model.entities.grep(Sketchup::Edge).length }.to_json
  end

  # Creates a group containing a line.
  # @return [String] JSON: {"groups": 1}
  def self.group_create_with_line
    model = Sketchup.active_model
    model.start_operation('Add Group', true)
    group = model.entities.add_group
    group.entities.add_line([0, 0, 0], [1.m, 0, 0])
    model.commit_operation
    { groups: model.entities.grep(Sketchup::Group).length }.to_json
  end

  # Adds a face and selects it.
  # @return [String] JSON: {"selected": 1}
  def self.selection_add_face
    model = Sketchup.active_model
    model.start_operation('Add and Select', true)
    face = model.entities.add_face([0, 0, 0], [1.m, 0, 0], [1.m, 1.m, 0], [0, 1.m, 0])
    model.selection.add(face)
    model.commit_operation
    { selected: model.selection.length }.to_json
  end

  # Creates a layer/tag named 'TestLayer'.
  # @return [String] JSON: {"name": "TestLayer"}
  def self.layer_create
    model = Sketchup.active_model
    layer = model.layers.add('TestLayer')
    { name: layer.name }.to_json
  end

  # Creates a blue material.
  # @return [String] JSON: {"name": "BlueMaterial", "count": N}
  def self.material_create_blue
    model = Sketchup.active_model
    mat = model.materials.add('BlueMaterial')
    mat.color = Sketchup::Color.new(0, 0, 255)
    { name: mat.name, count: model.materials.length }.to_json
  end

  # Sets camera to look at origin from (10m, 10m, 10m).
  # @return [String] JSON: {"eye": [10.0, 10.0, 10.0]}
  def self.camera_set_position
    model = Sketchup.active_model
    camera = model.active_view.camera
    eye = Geom::Point3d.new(10.m, 10.m, 10.m)
    target = Geom::Point3d.new(0, 0, 0)
    up = Geom::Vector3d.new(0, 0, 1)
    camera.set(eye, target, up)
    { eye: camera.eye.to_a.map { |v| v.to_m.round(1) } }.to_json
  end
end
