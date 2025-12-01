# frozen_string_literal: true

# Add decorative elements to the table
# This demonstrates modular scripting - extending the model with additional features

require_relative 'helpers'

# Module containing all decoration functions
# Reopens module from helpers.rb to add decoration-specific functions
module SupexSimpleTable
  # Creates a trim material with darker brown color
  # Uses recreate_material for idempotence
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param tag [String] Tag value for idempotence (default: 'decorations_example')
  # @return [Sketchup::Material] The created trim material
  def self.create_trim_material(model, tag = 'decorations_example')
    recreate_material(model, 'Trim', Sketchup::Color.new(101, 67, 33), tag)
  end

  # Helper to union multiple groups and optionally explode the result
  # When explode: true, geometry is merged into the parent entities collection
  #
  # @param groups [Array<Sketchup::Group>] Array of groups to union
  # @param explode [Boolean] Whether to explode the result (default: true)
  # @return [nil] When explode: true (geometry merged into parent)
  # @return [Sketchup::Group] When explode: false (returns the union result)
  def self.union_groups(groups, explode: true)
    return nil if groups.empty?

    result = groups[0]
    groups[1..].each do |group|
      result = result.union(group)
    end

    if explode
      result.explode
      nil # Geometry merged into parent, no return value needed
    else
      result
    end
  end

  # Creates decorative trim geometry around table edges
  #
  # @param parent_entities [Sketchup::Entities] Parent entities collection
  # @param params [Hash] Parameters for trim creation
  # @option params [Length] :table_length Table length (required)
  # @option params [Length] :table_width Table width (required)
  # @option params [Length] :table_height Height of table top surface (required)
  # @option params [Length] :trim_height Height of trim (required)
  # @option params [Length] :trim_width Width of trim overhang (required)
  # @return [Sketchup::Group] The created trim group
  def self.create_decorative_trim(parent_entities, params = {})
    # Extract required parameters
    table_length = params[:table_length]
    table_width = params[:table_width]
    table_height = params[:table_height]
    trim_height = params[:trim_height]
    trim_width = params[:trim_width]

    # Validate required parameters
    required = { table_length: table_length, table_width: table_width,
                 table_height: table_height, trim_height: trim_height,
                 trim_width: trim_width }
    missing = required.select { |_k, v| v.nil? }.keys
    raise ArgumentError, "Missing required parameters: #{missing.join(', ')}" unless missing.empty?

    trim_group = parent_entities.add_group
    trim_group.name = 'Decorative Trim'

    # Create trim as 4 boxes with symmetric overhang on all sides
    te = trim_group.entities
    z1 = table_height
    z2 = table_height + trim_height
    tw = trim_width

    # Create all trim boxes as separate groups
    boxes = []

    # Front trim: extends full width with overhang, sits on front edge
    boxes << create_box(te, -tw, -tw, z1, table_length + tw, 0, z2)

    # Back trim: extends full width with overhang, sits on back edge
    boxes << create_box(te, -tw, table_width, z1, table_length + tw, table_width + tw, z2)

    # Left trim: fits between front/back (no corner overlap)
    boxes << create_box(te, -tw, 0, z1, 0, table_width, z2)

    # Right trim: fits between front/back (no corner overlap)
    boxes << create_box(te, table_length, 0, z1, table_length + tw, table_width, z2)

    # Union all boxes together and explode into trim_group
    union_groups(boxes)

    trim_group
  end

  # Creates decorative trim for a table
  # Pure geometry function - creates trim based on table dimensions
  #
  # @param table_group [Sketchup::Group] The table group to add trim to
  # @param params [Hash] Optional parameters with defaults
  # @option params [Length] :trim_height Height of trim (default: 0.01m)
  # @option params [Length] :trim_width Width of trim overhang (default: 0.01m)
  # @return [Sketchup::Group] The created trim group (without attributes)
  # @raise [RuntimeError] If table top not found inside table group
  def self.create_table_decorations(table_group, params = {})
    # Get model from table_group
    model = table_group.model

    # Extract parameters with defaults
    trim_height = params[:trim_height] || 0.01.m
    trim_width = params[:trim_width] || 0.01.m

    # Find table top inside the table group
    table_top = table_group.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table Top' }
    raise 'Table top not found inside Table group!' unless table_top

    # Get table dimensions from existing geometry in the table group's local space
    inv = table_group.transformation.inverse
    corners = (0..7).map { |i| table_top.bounds.corner(i).transform(inv) }
    xs = corners.map(&:x)
    ys = corners.map(&:y)
    zs = corners.map(&:z)
    table_length = xs.max - xs.min
    table_width  = ys.max - ys.min
    table_height = zs.max # top surface height in group space

    # Create decorative trim (pure geometry, no cleanup here)
    trim_group = create_decorative_trim(
      table_group.entities,
      table_length: table_length,
      table_width: table_width,
      table_height: table_height,
      trim_height: trim_height,
      trim_width: trim_width
    )

    # Apply material to the trim
    trim_material = create_trim_material(model)
    trim_group.material = trim_material

    trim_group
  end

  # Example usage with default settings
  # Orchestrates decoration addition with transaction management
  #
  # @api orchestration
  # @return [void]
  def self.example_decorations
    model = Sketchup.active_model
    # Work at model root to avoid nesting when user is editing a group
    entities = model.entities

    # Configuration (single source of truth)
    table_name = 'Table'

    # Start operation for undo/redo support
    model.start_operation('Add Table Decorations', true)

    begin
      # Find the table group (orchestration concern)
      table_group = entities.find { |e| e.is_a?(Sketchup::Group) && e.name == table_name }
      raise 'Table not found! Create a table first.' unless table_group

      # Remove old trim if exists (idempotence - orchestration concern)
      table_group.entities.grep(Sketchup::Group).select do |g|
        g.name == 'Decorative Trim'
      end.each(&:erase!)

      # Create decorations (pure geometry)
      create_table_decorations(table_group)

      # NOTE: Trim is nested inside the Table group, so no metadata needed at root level
      # The trim group itself gets erased/recreated on re-run for idempotence

      # Commit the operation
      model.commit_operation

      puts 'Decorative trim added successfully!'
      puts 'The table now has enhanced visual detail'
      puts 'Use take_screenshot() to see the updated model'
    rescue StandardError => e
      # Abort operation on error
      model.abort_operation
      puts "Error adding decorations: #{e.message}"
      raise
    end
  end
end

if false # rubocop:disable Lint/LiteralAsCondition
  SupexSimpleTable.example_decorations
end
