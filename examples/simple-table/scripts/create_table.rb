# Create a simple wooden table in SketchUp
# This script demonstrates project-based workflow with Supex

model = Sketchup.active_model
# Work in model root to avoid nesting when user is editing a group.
entities = model.entities

# Start operation for undo/redo support
model.start_operation('Create Simple Table', true)

begin
  # Table dimensions (in meters)
  table_length = 1.2.m
  table_width = 0.8.m
  table_height = 0.75.m
  top_thickness = 0.04.m
  leg_size = 0.06.m
  leg_inset = 0.05.m

  # Create wood material
  wood_material = model.materials.add('Wood')
  wood_material.color = Sketchup::Color.new(139, 69, 19) # Saddle brown

  # Create main table group
  main_table = entities.add_group
  main_table.name = 'Table'

  # Create table top as a group inside main table
  table_top = main_table.entities.add_group
  table_top.name = 'Table Top'

  # Create face at the bottom of the table top
  top_face = table_top.entities.add_face(
    [0, 0, table_height - top_thickness],
    [table_length, 0, table_height - top_thickness],
    [table_length, table_width, table_height - top_thickness],
    [0, table_width, table_height - top_thickness]
  )
  # Extrude upward to create thickness
  top_face.pushpull(top_thickness)

  # Apply material to all faces
  table_top.entities.each { |e| e.material = wood_material if e.is_a?(Sketchup::Face) }

  # Create table legs group inside main table
  table_legs_group = main_table.entities.add_group
  table_legs_group.name = 'Table Legs'

  # Create four table legs
  leg_positions = [
    [leg_inset, leg_inset],                                    # Front left
    [table_length - leg_inset - leg_size, leg_inset],         # Front right
    [leg_inset, table_width - leg_inset - leg_size],          # Back left
    [table_length - leg_inset - leg_size, table_width - leg_inset - leg_size] # Back right
  ]

  leg_positions.each_with_index do |pos, i|
    leg = table_legs_group.entities.add_group
    leg.name = "Table Leg #{i + 1}"

    # Create square leg profile at ground level
    # Vertices in clockwise order (viewed from above) so normal points down
    x, y = pos
    leg_face = leg.entities.add_face(
      [x, y, 0],
      [x, y + leg_size, 0],
      [x + leg_size, y + leg_size, 0],
      [x + leg_size, y, 0]
    )

    # Extrude up to meet the table top (negative value since normal points down)
    leg_face.pushpull(-(table_height - top_thickness))

    # Apply material to all faces of the leg
    leg.entities.each { |e| e.material = wood_material if e.is_a?(Sketchup::Face) }
  end

  # Commit the operation
  model.commit_operation

  puts 'Table created successfully!'
  puts "Dimensions: #{table_length.to_m}m x #{table_width.to_m}m x #{table_height.to_m}m"
  puts 'Structure: Table > Table Top + Table Legs (4 legs)'
  puts 'Use get_model_info() or take_screenshot() to verify the result'

rescue StandardError => e
  # Abort operation on error
  model.abort_operation
  puts "Error creating table: #{e.message}"
  raise
end
