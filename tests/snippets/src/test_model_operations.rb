# Ruby snippets for test_model_operations.py
# All functions wrapped in SupexTestSnippets module to prevent naming conflicts

module SupexTestSnippets
  def self.geom_create_cube
    model = Sketchup.active_model
    model.start_operation('Create Cube', true)
    group = model.entities.add_group
    face = group.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    face.pushpull(-1.m)
    model.commit_operation
    {faces: group.entities.grep(Sketchup::Face).length, edges: group.entities.grep(Sketchup::Edge).length}
  end

  def self.geom_create_circle
    model = Sketchup.active_model
    model.start_operation('Create Circle', true)
    center = Geom::Point3d.new(0, 0, 0)
    normal = Geom::Vector3d.new(0, 0, 1)
    edges = model.entities.add_circle(center, normal, 1.m)
    model.commit_operation
    edges.length
  end

  def self.geom_create_cylinder
    model = Sketchup.active_model
    model.start_operation('Create Cylinder', true)
    # Create circle - SketchUp creates edges but may not create face automatically
    center = Geom::Point3d.new(0, 0, 0)
    normal = Geom::Vector3d.new(0, 0, 1)
    radius = 0.5.m
    # Create points for a circle
    points = []
    segments = 24
    (0...segments).each do |i|
      angle = (i.to_f / segments) * Math::PI * 2
      x = center.x + radius * Math.cos(angle)
      y = center.y + radius * Math.sin(angle)
      points << [x, y, center.z]
    end
    # Create face from points and extrude
    face = model.entities.add_face(points)
    face.pushpull(2.m) if face
    model.commit_operation
    model.entities.grep(Sketchup::Face).length
  end

  def self.group_create_named
    model = Sketchup.active_model
    model.start_operation('Create Group', true)
    group = model.entities.add_group
    group.entities.add_line([0,0,0], [1.m,0,0])
    group.name = 'TestGroup'
    model.commit_operation
    model.entities.grep(Sketchup::Group).first.name
  end

  def self.group_create_nested
    model = Sketchup.active_model
    model.start_operation('Nested Groups', true)
    outer = model.entities.add_group
    outer.name = 'Outer'
    inner = outer.entities.add_group
    inner.name = 'Inner'
    inner.entities.add_line([0,0,0], [1.m,0,0])
    model.commit_operation
    outer.entities.grep(Sketchup::Group).first.name
  end

  def self.component_create
    model = Sketchup.active_model
    model.start_operation('Create Component', true)
    defn = model.definitions.add('TestComponent')
    defn.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    instance = model.entities.add_instance(defn, IDENTITY)
    model.commit_operation
    model.definitions['TestComponent'].name
  end

  def self.component_create_multiple_instances
    model = Sketchup.active_model
    model.start_operation('Multiple Instances', true)
    defn = model.definitions.add('Box')
    defn.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    t1 = Geom::Transformation.new([0, 0, 0])
    t2 = Geom::Transformation.new([2.m, 0, 0])
    t3 = Geom::Transformation.new([4.m, 0, 0])
    model.entities.add_instance(defn, t1)
    model.entities.add_instance(defn, t2)
    model.entities.add_instance(defn, t3)
    model.commit_operation
    model.entities.grep(Sketchup::ComponentInstance).length
  end

  def self.material_create_and_apply
    model = Sketchup.active_model
    model.start_operation('Create Material', true)
    mat = model.materials.add('RedMaterial')
    mat.color = Sketchup::Color.new(255, 0, 0)
    face = model.entities.add_face([0,0,0], [1.m,0,0], [1.m,1.m,0], [0,1.m,0])
    face.material = mat
    model.commit_operation
    face.material.name
  end

  def self.material_create_transparent
    model = Sketchup.active_model
    model.start_operation('Transparent Material', true)
    mat = model.materials.add('GlassMaterial')
    mat.color = Sketchup::Color.new(200, 200, 255)
    mat.alpha = 0.5
    model.commit_operation
    model.materials['GlassMaterial'].alpha
  end
end
