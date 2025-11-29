# Add decorative elements to the table
# This demonstrates modular scripting - extending the model with additional features

model = Sketchup.active_model
# Work at model root to avoid nesting inside the currently open group/component.
entities = model.entities

model.start_operation('Add Table Decorations', true)

begin
  # Add a decorative edge trim around table top
  # This shows how to build upon existing geometry

  # Find the table group first, then table top inside it
  table_group = entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table' }

  unless table_group
    puts 'Table not found! Run create_table.rb first.'
    model.abort_operation
    raise 'Table not found'
  end

  table_top = table_group.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table Top' }

  unless table_top
    puts 'Table top not found inside Table group!'
    model.abort_operation
    raise 'Table top not found'
  end

  # Get table dimensions from existing geometry in the table group's local space
  inv = table_group.transformation.inverse
  corners = (0..7).map { |i| table_top.bounds.corner(i).transform(inv) }
  xs = corners.map(&:x)
  ys = corners.map(&:y)
  zs = corners.map(&:z)
  table_length = xs.max - xs.min
  table_width  = ys.max - ys.min
  table_height = zs.max          # top surface height in group space

  trim_height = 0.01.m
  trim_width  = 0.01.m  # small overhang on all sides

  # Create / reuse decorative trim material
  trim_material = model.materials['Trim'] || model.materials.add('Trim')
  trim_material.color = Sketchup::Color.new(101, 67, 33) # Darker brown

  # Add trim around table edge; keep it grouped with the table so moves stay in sync
  # Remove old trim if script is re-run
  table_group.entities.grep(Sketchup::Group).select { |g| g.name == 'Decorative Trim' }.each(&:erase!)

  trim_group = table_group.entities.add_group
  trim_group.name = 'Decorative Trim'

  # Create trim as 4 boxes with symmetric overhang on all sides
  te = trim_group.entities
  z1 = table_height
  z2 = table_height + trim_height
  tw = trim_width

  # Helper to create a box from min/max corners with consistent normals
  def create_box(entities, x1, y1, z1, x2, y2, z2)
    pts = [
      Geom::Point3d.new(x1, y1, z1),
      Geom::Point3d.new(x2, y1, z1),
      Geom::Point3d.new(x2, y2, z1),
      Geom::Point3d.new(x1, y2, z1)
    ]

    face = entities.add_face(pts)
    face.reverse! if face.normal.z < 0 # ensure front face points up
    face.pushpull(z2 - z1)             # generates side faces with correct orientation
  end

  # Front trim: extends full width with overhang, sits on front edge
  create_box(te, -tw, -tw, z1, table_length + tw, 0, z2)

  # Back trim: extends full width with overhang, sits on back edge
  create_box(te, -tw, table_width, z1, table_length + tw, table_width + tw, z2)

  # Left trim: fits between front/back (no corner overlap)
  create_box(te, -tw, 0, z1, 0, table_width, z2)

  # Right trim: fits between front/back (no corner overlap)
  create_box(te, table_length, 0, z1, table_length + tw, table_width, z2)

  # Ensure faces point outward from the trim bounding box and apply material on both sides
  center = trim_group.bounds.center
  trim_group.entities.grep(Sketchup::Face).each do |f|
    c = f.bounds.center
    outward = Geom::Vector3d.new(c.x - center.x, c.y - center.y, c.z - center.z)
    f.reverse! if outward.valid? && outward.dot(f.normal) < 0
    f.material = trim_material
    f.back_material = trim_material
  end

  model.commit_operation

  puts 'Decorative trim added successfully!'
  puts 'The table now has enhanced visual detail'
  puts 'Use take_screenshot() to see the updated model'

rescue StandardError => e
  model.abort_operation
  puts "Error adding decorations: #{e.message}"
  raise
end
