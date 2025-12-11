# frozen_string_literal: true

# Create a simple wooden table in SketchUp
# This script demonstrates procedural programming approach with Supex

require_relative 'helpers'
require_relative 'sketchup_extensions'

# Module containing all table creation functions
# Prevents namespace pollution when used as a library
# Reopens module from helpers.rb to add table-specific functions
module SupexSimpleTable
  # Creates a wood material with saddle brown color
  # Uses recreate_material for idempotence
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param tag [String] Tag value for idempotence (default: IDENT_TABLE)
  # @return [Sketchup::Material] The created wood material
  def self.create_wood_material(model, tag = IDENT_TABLE)
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

    # Apply material to group
    table_top.material = material

    table_top
  end

  # Finds or creates a table leg component definition
  # Uses tag-based lookup to reuse existing definition and avoid leaking Table Leg#n
  # Note: Material should be applied at instance level, not in definition
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param leg_size [Length] Size of leg (square cross-section)
  # @param leg_height [Length] Height of leg
  # @return [Sketchup::ComponentDefinition] The leg component definition
  def self.find_or_create_leg_definition(model, leg_size, leg_height)
    leg_def_name = 'Table Leg'

    # First, try to find existing definition by tag
    existing_def = model.definitions.find do |d|
      d.get_attribute(ATTR_DICT, ATTR_KEY) == IDENT_TABLE
    end

    if existing_def
      # Clear and reuse existing definition
      existing_def.entities.clear!
      leg_def = existing_def
    else
      # Create new definition and tag it
      leg_def = model.definitions.add(leg_def_name)
      leg_def.set_attribute(ATTR_DICT, ATTR_KEY, IDENT_TABLE)
    end

    # Create square leg profile at origin
    # Vertices in clockwise order (viewed from above) so normal points down
    leg_face = leg_def.entities.add_face(
      [0, 0, 0],
      [0, leg_size, 0],
      [leg_size, leg_size, 0],
      [leg_size, 0, 0]
    )

    # Extrude up to create leg height (negative value since normal points down)
    leg_face.pushpull(-leg_height)

    leg_def
  end

  # Creates all four table legs using component instances
  # Uses a single component definition for efficiency
  #
  # @param parent_entities [Sketchup::Entities] Parent entities collection
  # @param table_length [Length] Table length
  # @param table_width [Length] Table width
  # @param leg_size [Length] Size of leg (square cross-section)
  # @param leg_inset [Length] Inset from edge
  # @param leg_height [Length] Height of legs
  # @param material [Sketchup::Material] Material to apply
  # @return [Sketchup::Group] The created legs group containing 4 component instances
  def self.create_table_legs(parent_entities, table_length, table_width, leg_size, leg_inset,
                             leg_height, material)
    model = parent_entities.model
    table_legs_group = parent_entities.add_group
    table_legs_group.name = 'Table Legs'

    # Find or create leg component definition (reuses existing to avoid leaking definitions)
    leg_def = find_or_create_leg_definition(model, leg_size, leg_height)

    # Calculate positions for four legs
    leg_positions = [
      [leg_inset, leg_inset], # Front left
      [table_length - leg_inset - leg_size, leg_inset], # Front right
      [leg_inset, table_width - leg_inset - leg_size], # Back left
      [table_length - leg_inset - leg_size, table_width - leg_inset - leg_size] # Back right
    ]

    # Place 4 instances of the leg component with material applied at instance level
    leg_positions.each_with_index do |pos, i|
      x_pos, y_pos = pos
      transform = Geom::Transformation.new([x_pos, y_pos, 0])
      instance = table_legs_group.entities.add_instance(leg_def, transform)
      instance.name = "Table Leg #{i + 1}"
      instance.material = material
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
  # @param effective_params [Hash, nil] Optional output hash to receive effective parameter values
  # @return [Sketchup::Group] The created table group (without name or attributes)
  def self.create_simple_table(entities, params = {}, effective_params = nil)
    # Get model from entities
    model = entities.model

    # Extract parameters with defaults
    table_length = params[:table_length] || 1.2.m
    table_width = params[:table_width] || 0.8.m
    table_height = params[:table_height] || 0.75.m
    top_thickness = params[:top_thickness] || 0.04.m
    leg_size = params[:leg_size] || 0.06.m
    leg_inset = params[:leg_inset] || 0.05.m

    # Validate all dimensions are positive
    validate_positive_lengths(
      table_length: table_length, table_width: table_width, table_height: table_height,
      top_thickness: top_thickness, leg_size: leg_size, leg_inset: leg_inset
    )

    # Fill effective_params if provided
    if effective_params
      effective_params[:table_length] = table_length
      effective_params[:table_width] = table_width
      effective_params[:table_height] = table_height
      effective_params[:top_thickness] = top_thickness
      effective_params[:leg_size] = leg_size
      effective_params[:leg_inset] = leg_inset
    end

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

  # Verifies that a table group has expected structure
  # Checks for required children and nonzero bounding box
  #
  # @param table_group [Sketchup::Group] The table group to verify
  # @return [Hash] Verification results with :valid, :errors, :children keys
  def self.verify_table(table_group)
    errors = []
    children = {}

    # Check for Table Top
    table_top = table_group.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table Top' }
    if table_top
      children[:table_top] = true
    else
      errors << 'Missing Table Top group'
      children[:table_top] = false
    end

    # Check for Table Legs
    table_legs = table_group.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table Legs' }
    if table_legs
      children[:table_legs] = true
      # Count leg instances
      leg_count = table_legs.entities.grep(Sketchup::ComponentInstance).count
      children[:leg_count] = leg_count
      errors << "Expected 4 leg instances, found #{leg_count}" if leg_count != 4
    else
      errors << 'Missing Table Legs group'
      children[:table_legs] = false
    end

    # Check bounding box is nonzero
    bounds = table_group.bounds
    if bounds.empty?
      errors << 'Bounding box is empty'
    elsif bounds.width.zero? || bounds.height.zero? || bounds.depth.zero?
      errors << 'Bounding box has zero dimension'
    end

    {
      valid: errors.empty?,
      errors: errors,
      children: children
    }
  end

  # Describes a table's dimensions for assertions
  # Returns effective dimensions from the table geometry
  #
  # @param table_group [Sketchup::Group] The table group to describe
  # @return [Hash] Table dimensions: length, width, height (all in model units)
  def self.describe_table(table_group)
    bounds = table_group.bounds

    # Find table top for more accurate height measurement
    table_top = table_group.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table Top' }
    table_height = table_top ? table_top.bounds.max.z : bounds.max.z

    {
      length: bounds.width,  # X dimension
      width: bounds.depth,   # Y dimension
      height: table_height,  # Z dimension (top of table)
      bounds: {
        min: bounds.min.to_a,
        max: bounds.max.to_a
      }
    }
  end

  # Example usage with default dimensions
  # Orchestrates table creation with transaction management
  #
  # @param params [Hash] Optional parameters passed to create_simple_table
  # @option params [String] :ident Identifier for idempotence (default: IDENT_TABLE)
  # @api orchestration
  # @return [Sketchup::Group] The created table group
  def self.example_table(params = {})
    model = Sketchup.active_model
    # Work in model root to avoid nesting when user is editing a group.
    entities = model.entities

    # Configuration
    ident = params[:ident] || IDENT_TABLE
    table_name = 'Table'

    # Start operation for undo/redo support
    model.start_operation('Create Simple Table', true)

    begin
      # Cleanup previous example instances (idempotent)
      cleanup_by_name_and_attribute(entities, table_name, ATTR_DICT, ATTR_KEY, ident)

      # Create the table (clean geometry without metadata)
      effective = {}
      table = create_simple_table(entities, params, effective)

      # Apply metadata (orchestration concern)
      table.name = table_name
      table.set_attribute(ATTR_DICT, ATTR_KEY, ident)

      # Commit the operation
      model.commit_operation

      l = effective[:table_length].to_m
      w = effective[:table_width].to_m
      h = effective[:table_height].to_m
      puts 'Table created successfully!'
      puts "Dimensions: #{l}m x #{w}m x #{h}m"
      puts 'Structure: Table > Table Top + Table Legs (4 component instances)'
      puts 'Use get_model_info() or take_screenshot() to verify the result'

      table
    rescue StandardError => e
      # Abort operation on error
      model.abort_operation
      puts "Error creating table: #{e.message}"
      puts e.backtrace.first(5).join("\n") if e.backtrace
      raise
    end
  end

  # Full example: creates table with decorations and vase
  # Convenience orchestration that runs all example methods in sequence
  #
  # @param params [Hash] Optional parameters passed to example_table
  # @return [Sketchup::Group] The created table group (with decorations and vase)
  # @api orchestration
  def self.example_full(params = {})
    # Require decorations and vase scripts
    require_relative 'add_decorations'
    require_relative 'add_vase'

    # Create table first
    table = example_table(params)

    # Add decorations
    example_decorations

    # Add vase
    example_vase

    puts ''
    puts 'Full table setup complete!'
    puts 'Table includes: top, legs, decorative trim, and vase'

    table
  end
end

if false # rubocop:disable Lint/LiteralAsCondition
  SupexSimpleTable.example_table
  SupexSimpleTable.example_table(table_height: 1.m, ident: 'basic_table_bar').move_to(3.m, 0)
  SupexSimpleTable.example_table(table_length: 2.m, ident: 'basic_table_long').move_to(0, 2.m)
  SupexSimpleTable.example_table(table_height: 0.5.m, ident: 'basic_table_low').move_to(3.m, 2.m)
end
