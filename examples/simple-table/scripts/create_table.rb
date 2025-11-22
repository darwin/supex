# frozen_string_literal: true

# Create a simple wooden table in SketchUp
# This script demonstrates procedural programming approach with Supex

# Module containing all table creation functions
# Prevents namespace pollution when used as a library
module SupexBasicTable
  # Creates a wood material with saddle brown color
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @return [Sketchup::Material] The created wood material
  def self.create_wood_material(model)
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
  def self.create_table_top(parent_entities, length, width, height, thickness, material)
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
  def self.create_table_leg(parent_entities, x, y, leg_size, leg_height, material, index)
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
  def self.create_table_legs(parent_entities, table_length, table_width, leg_size, leg_inset, leg_height, material)
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

  # Creates a complete table with top and legs
  #
  # @param entities [Sketchup::Entities] Where to create the table
  # @param model [Sketchup::Model] The active SketchUp model
  # @param table_length [Length] Table length
  # @param table_width [Length] Table width
  # @param table_height [Length] Total table height
  # @param top_thickness [Length] Thickness of table top
  # @param leg_size [Length] Size of leg (square cross-section)
  # @param leg_inset [Length] Inset from edge for leg placement
  # @return [Sketchup::Group] The created table group
  def self.create_simple_table(entities, model, table_length, table_width, table_height, top_thickness, leg_size,
                                leg_inset)
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

    main_table
  end

  # Example usage with default dimensions
  # Orchestrates table creation with transaction management
  def self.example
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

      # Create the table
      create_simple_table(entities, model, table_length, table_width, table_height, top_thickness, leg_size,
                          leg_inset)

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
  end
end
