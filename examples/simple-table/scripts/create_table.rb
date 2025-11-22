# frozen_string_literal: true

# Create a simple wooden table in SketchUp
# This script demonstrates procedural programming approach with Supex

# Creates a wood material with saddle brown color
#
# @param model [Sketchup::Model] The active SketchUp model
# @return [Sketchup::Material] The created wood material
def create_wood_material(model)
  wood_material = model.materials.add('Wood')
  wood_material.color = Sketchup::Color.new(139, 69, 19) # Saddle brown
  wood_material
end

# Creates a table top as a group
#
# @param parent_entities [Sketchup::Entities] Parent entities collection
# @param length [Length] Table length
# @param width [Length] Table width
# @param height [Length] Height to bottom of table top
# @param thickness [Length] Thickness of table top
# @param material [Sketchup::Material] Material to apply
# @return [Sketchup::Group] The created table top group
def create_table_top(parent_entities, length, width, height, thickness, material)
  table_top = parent_entities.add_group
  table_top.name = 'Table Top'

  # Create face at the bottom of the table top
  top_face = table_top.entities.add_face(
    [0, 0, height - thickness],
    [length, 0, height - thickness],
    [length, width, height - thickness],
    [0, width, height - thickness]
  )

  # Extrude upward to create thickness
  top_face.pushpull(thickness)

  # Apply material to all faces
  table_top.entities.each { |e| e.material = material if e.is_a?(Sketchup::Face) }

  table_top
end

# Creates a single table leg as a group
#
# @param parent_entities [Sketchup::Entities] Parent entities collection
# @param x [Length] X position of leg
# @param y [Length] Y position of leg
# @param leg_size [Length] Size of leg (square cross-section)
# @param leg_height [Length] Height of leg
# @param material [Sketchup::Material] Material to apply
# @param index [Integer] Leg index for naming (1-based)
# @return [Sketchup::Group] The created leg group
def create_table_leg(parent_entities, x, y, leg_size, leg_height, material, index)
  leg = parent_entities.add_group
  leg.name = "Table Leg #{index}"

  # Create square leg profile at ground level
  # Vertices in clockwise order (viewed from above) so normal points down
  leg_face = leg.entities.add_face(
    [x, y, 0],
    [x, y + leg_size, 0],
    [x + leg_size, y + leg_size, 0],
    [x + leg_size, y, 0]
  )

  # Extrude up to meet the table top (negative value since normal points down)
  leg_face.pushpull(-leg_height)

  # Apply material to all faces of the leg
  leg.entities.each { |e| e.material = material if e.is_a?(Sketchup::Face) }

  leg
end

# Creates all four table legs in a group
#
# @param parent_entities [Sketchup::Entities] Parent entities collection
# @param table_length [Length] Table length
# @param table_width [Length] Table width
# @param leg_size [Length] Size of leg (square cross-section)
# @param leg_inset [Length] Inset from edge
# @param leg_height [Length] Height of legs
# @param material [Sketchup::Material] Material to apply
# @return [Sketchup::Group] The created legs group
def create_table_legs(parent_entities, table_length, table_width, leg_size, leg_inset, leg_height, material)
  table_legs_group = parent_entities.add_group
  table_legs_group.name = 'Table Legs'

  # Calculate positions for four legs
  leg_positions = [
    [leg_inset, leg_inset], # Front left
    [table_length - leg_inset - leg_size, leg_inset],         # Front right
    [leg_inset, table_width - leg_inset - leg_size],          # Back left
    [table_length - leg_inset - leg_size, table_width - leg_inset - leg_size] # Back right
  ]

  # Create each leg
  leg_positions.each_with_index do |pos, i|
    x, y = pos
    create_table_leg(table_legs_group.entities, x, y, leg_size, leg_height, material, i + 1)
  end

  table_legs_group
end

# Main execution
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
  wood_material = create_wood_material(model)

  # Create main table group
  main_table = entities.add_group
  main_table.name = 'Table'

  # Create table top
  create_table_top(main_table.entities, table_length, table_width, table_height, top_thickness, wood_material)

  # Create table legs
  leg_height = table_height - top_thickness
  create_table_legs(main_table.entities, table_length, table_width, leg_size, leg_inset, leg_height, wood_material)

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
