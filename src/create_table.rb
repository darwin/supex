# frozen_string_literal: true

# Create a simple wooden table in SketchUp
# This script demonstrates procedural programming approach with Supex

require_relative 'helpers'

# Module containing all table creation functions
# Prevents namespace pollution when used as a library
# Reopens module from helpers.rb to add table-specific functions
module SupexSimpleTable
  # Creates a wood material with saddle brown color
  # Uses recreate_material for idempotence
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param tag [String] Tag value for idempotence (default: 'basic_table_example')
  # @return [Sketchup::Material] The created wood material
  def self.create_wood_material(model, tag = 'basic_table_example')
    recreate_material(model, 'Wood', Sketchup::Color.new(139, 69, 19), tag)
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
  # @param x_pos [Length] X position of leg
  # @param y_pos [Length] Y position of leg
  # @param leg_size [Length] Size of leg (square cross-section)
  # @param leg_height [Length] Height of leg
  # @param material [Sketchup::Material] Material to apply
  # @param index [Integer] Leg index for naming (1-based)
  # @return [Sketchup::Group] The created leg group
  def self.create_table_leg(parent_entities, x_pos, y_pos, leg_size, leg_height, material, index)
    leg = parent_entities.add_group
    leg.name = "Table Leg #{index}"

    # Create square leg profile at ground level
    # Vertices in clockwise order (viewed from above) so normal points down
    leg_face = leg.entities.add_face(
      [x_pos, y_pos, 0],
      [x_pos, y_pos + leg_size, 0],
      [x_pos + leg_size, y_pos + leg_size, 0],
      [x_pos + leg_size, y_pos, 0]
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
  def self.create_table_legs(parent_entities, table_length, table_width, leg_size, leg_inset,
                             leg_height, material)
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
      x_pos, y_pos = pos
      create_table_leg(table_legs_group.entities, x_pos, y_pos, leg_size, leg_height, material,
                       i + 1)
    end

    table_legs_group
  end

  # Creates a complete table with top and legs
  # Returns a clean geometry object without metadata (name, attributes)
  # Metadata should be applied at orchestration level
  #
  # @param entities [Sketchup::Entities] Where to create the table (model via entities.model)
  # @param params [Hash] Optional parameters with defaults
  # @option params [Length] :table_length Table length (default: 1.2m)
  # @option params [Length] :table_width Table width (default: 0.8m)
  # @option params [Length] :table_height Total table height (default: 0.75m)
  # @option params [Length] :top_thickness Thickness of table top (default: 0.04m)
  # @option params [Length] :leg_size Size of leg square cross-section (default: 0.06m)
  # @option params [Length] :leg_inset Inset from edge for leg placement (default: 0.05m)
  # @return [Sketchup::Group] The created table group (without name or attributes)
  def self.create_simple_table(entities, params = {})
    # Get model from entities
    model = entities.model

    # Extract parameters with defaults
    table_length = params[:table_length] || 1.2.m
    table_width = params[:table_width] || 0.8.m
    table_height = params[:table_height] || 0.75.m
    top_thickness = params[:top_thickness] || 0.04.m
    leg_size = params[:leg_size] || 0.06.m
    leg_inset = params[:leg_inset] || 0.05.m

    # Create wood material
    wood_material = create_wood_material(model)

    # Create main table group (no metadata - orchestration will add name and attributes)
    main_table = entities.add_group

    # Create table top
    create_table_top(main_table.entities, table_length, table_width, table_height, top_thickness,
                     wood_material)

    # Create table legs
    leg_height = table_height - top_thickness
    create_table_legs(main_table.entities, table_length, table_width, leg_size, leg_inset,
                      leg_height, wood_material)

    main_table
  end

  # Example usage with default dimensions
  # Orchestrates table creation with transaction management
  #
  # @api orchestration
  # @return [void]
  def self.example_table
    model = Sketchup.active_model
    # Work in model root to avoid nesting when user is editing a group.
    entities = model.entities

    # Configuration (single source of truth)
    table_name = 'Table'
    attribute_type = 'basic_table_example'

    # Start operation for undo/redo support
    model.start_operation('Create Simple Table', true)

    begin
      # Cleanup previous example instances (idempotent)
      cleanup_by_name_and_attribute(entities, table_name, 'supex', 'type', attribute_type)

      # Create the table (clean geometry without metadata, using defaults)
      table = create_simple_table(entities)

      # Apply metadata (orchestration concern)
      table.name = table_name
      table.set_attribute('supex', 'type', attribute_type)

      # Commit the operation
      model.commit_operation

      puts 'Table created successfully!'
      puts 'Dimensions: 1.2m x 0.8m x 0.75m (default)'
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

if false # rubocop:disable Lint/LiteralAsCondition
  SupexSimpleTable.example_table
end
