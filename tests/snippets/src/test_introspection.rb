# Ruby snippets for test_introspection.py
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts

module SupexTestSnippets
  def self.geom_add_face
    model = Sketchup.active_model
    model.start_operation('Add Geometry', true)
    model.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    model.commit_operation
  end

  def self.geom_add_edges
    model = Sketchup.active_model
    model.start_operation('Add Edges', true)
    model.entities.add_line([0,0,0], [1.m,0,0])
    model.entities.add_line([1.m,0,0], [1.m,1.m,0])
    model.commit_operation
  end

  def self.group_create_with_line
    model = Sketchup.active_model
    model.start_operation('Add Group', true)
    group = model.entities.add_group
    group.entities.add_line([0,0,0], [1.m,0,0])
    model.commit_operation
  end

  def self.selection_add_face
    model = Sketchup.active_model
    model.start_operation('Add and Select', true)
    face = model.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    model.selection.add(face)
    model.commit_operation
    model.selection.length
  end

  def self.layer_create
    model = Sketchup.active_model
    model.layers.add('TestLayer')
    model.layers['TestLayer'].name
  end

  def self.material_create_blue
    model = Sketchup.active_model
    mat = model.materials.add('BlueMaterial')
    mat.color = Sketchup::Color.new(0, 0, 255)
    model.materials.length
  end

  def self.camera_set_position
    model = Sketchup.active_model
    camera = model.active_view.camera
    eye = Geom::Point3d.new(10.m, 10.m, 10.m)
    target = Geom::Point3d.new(0, 0, 0)
    up = Geom::Vector3d.new(0, 0, 1)
    camera.set(eye, target, up)
    camera.eye.to_a.map { |v| v.to_m.round(1) }
  end
end
