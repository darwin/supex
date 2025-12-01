# frozen_string_literal: true

# Add a decorative vase to the table
# This demonstrates creating curved 3D geometry using Follow Me (revolution)

require_relative 'helpers'

# Module containing all vase functions
# Reopens module from helpers.rb to add vase-specific functions
module SupexSimpleTable
  # Creates a ceramic material with blue color
  # Uses recreate_material for idempotence
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param tag [String] Tag value for idempotence (default: 'vase_example')
  # @return [Sketchup::Material] The created ceramic material
  def self.create_ceramic_material(model, tag = 'vase_example')
    recreate_material(model, 'Blue Ceramic', Sketchup::Color.new(70, 130, 180), tag)
  end

  # Generates profile points for a classic vase shape
  # Creates a smooth curve from base through belly to neck
  #
  # @param params [Hash] Vase dimension parameters
  # @option params [Length] :height Total height of vase
  # @option params [Length] :base_radius Radius at base
  # @option params [Length] :mid_radius Radius at widest point (belly)
  # @option params [Length] :neck_radius Radius at top opening
  # @return [Array<Geom::Point3d>] Array of points defining the vase profile
  def self.create_vase_profile_points(params)
    height = params[:height]
    base_radius = params[:base_radius]
    mid_radius = params[:mid_radius]
    neck_radius = params[:neck_radius]

    # Create smooth profile using bezier-like interpolation
    # Profile is in XZ plane, will be revolved around Z axis
    points = []

    # Bottom center (for closed base)
    points << Geom::Point3d.new(0, 0, 0)

    # Base edge
    points << Geom::Point3d.new(base_radius, 0, 0)

    # Lower curve (base to belly) - 4 interpolation points
    (1..4).each do |i|
      t = i / 5.0
      z = height * 0.5 * t
      # Smooth interpolation from base to mid radius
      r = base_radius + (mid_radius - base_radius) * Math.sin(t * Math::PI / 2)
      points << Geom::Point3d.new(r, 0, z)
    end

    # Belly (widest point)
    points << Geom::Point3d.new(mid_radius, 0, height * 0.5)

    # Upper curve (belly to neck) - 4 interpolation points
    (1..4).each do |i|
      t = i / 5.0
      z = height * 0.5 + height * 0.4 * t
      # Smooth interpolation from mid to neck radius
      r = mid_radius - (mid_radius - neck_radius) * Math.sin(t * Math::PI / 2)
      points << Geom::Point3d.new(r, 0, z)
    end

    # Neck (top)
    points << Geom::Point3d.new(neck_radius, 0, height * 0.9)

    # Slight flare at rim
    points << Geom::Point3d.new(neck_radius + 0.005.m, 0, height)

    # Top center (for closed rim - thin wall effect)
    points << Geom::Point3d.new(0, 0, height)

    points
  end

  # Applies smooth/soft edges based on angle threshold
  # Equivalent to UI: View > Edge Style > Soften Edges slider
  # Note: No direct API exists for the Soften Edges dialog - iteration is required
  #
  # @param entities [Sketchup::Entities] Entities to smooth
  # @param angle_degrees [Numeric] Angle threshold in degrees (default: 20)
  # @return [void]
  def self.smooth_edges(entities, angle_degrees = 20)
    max_angle = angle_degrees.degrees
    entities.grep(Sketchup::Edge).each do |edge|
      next unless edge.faces.length == 2

      angle = edge.faces[0].normal.angle_between(edge.faces[1].normal)
      edge.soft = edge.smooth = (angle <= max_angle)
    end
  end

  # Creates a vase using Follow Me (revolution of profile)
  #
  # @param parent_entities [Sketchup::Entities] Parent entities collection
  # @param params [Hash] Vase parameters
  # @option params [Length] :height Total height (default: 0.15m)
  # @option params [Length] :base_radius Base radius (default: 0.03m)
  # @option params [Length] :mid_radius Belly radius (default: 0.05m)
  # @option params [Length] :neck_radius Neck radius (default: 0.025m)
  # @option params [Numeric] :smooth_angle Smooth edges angle in degrees (default: 20)
  # @return [Sketchup::Group] The created vase group
  def self.create_vase(parent_entities, params = {})
    # Extract parameters with defaults
    height = params[:height] || 0.15.m
    base_radius = params[:base_radius] || 0.03.m
    mid_radius = params[:mid_radius] || 0.05.m
    neck_radius = params[:neck_radius] || 0.025.m
    smooth_angle = params[:smooth_angle] || 20

    # Create vase group
    vase_group = parent_entities.add_group
    vase_group.name = 'Vase'
    entities = vase_group.entities

    # Get profile points
    profile_points = create_vase_profile_points(
      height: height,
      base_radius: base_radius,
      mid_radius: mid_radius,
      neck_radius: neck_radius
    )

    # Create the profile face in XZ plane
    profile_face = entities.add_face(profile_points)

    # Create circular path for Follow Me
    # Path is a full circle in XY plane at origin
    center = Geom::Point3d.new(0, 0, 0)
    path_edges = entities.add_circle(center, Z_AXIS, base_radius, 24)

    # Use Follow Me to revolve profile around the path
    profile_face.followme(path_edges)

    # Clean up the path edges (they're no longer needed)
    path_edges.each { |edge| edge.erase! if edge.valid? }

    # Apply smooth edges to the vase (20 degrees default)
    smooth_edges(vase_group.entities, smooth_angle)

    vase_group
  end

  # Creates a vase on the table surface
  # Finds table dimensions and positions vase accordingly
  #
  # @param table_group [Sketchup::Group] The table group to place vase on
  # @param params [Hash] Optional parameters with defaults
  # @option params [Length] :height Vase height (default: 0.15m)
  # @option params [Length] :base_radius Base radius (default: 0.03m)
  # @option params [Length] :mid_radius Belly radius (default: 0.05m)
  # @option params [Length] :neck_radius Neck radius (default: 0.025m)
  # @option params [Length] :offset_x X offset from table center (default: 0)
  # @option params [Length] :offset_y Y offset from table center (default: 0)
  # @return [Sketchup::Group] The created vase group (positioned on table)
  def self.create_table_vase(table_group, params = {})
    model = table_group.model

    # Extract offset parameters
    offset_x = params[:offset_x] || 0
    offset_y = params[:offset_y] || 0

    # Find table top inside the table group
    table_top = table_group.entities.find { |e| e.is_a?(Sketchup::Group) && e.name == 'Table Top' }
    raise 'Table top not found inside Table group!' unless table_top

    # Get table dimensions from existing geometry
    inv = table_group.transformation.inverse
    corners = (0..7).map { |i| table_top.bounds.corner(i).transform(inv) }
    xs = corners.map(&:x)
    ys = corners.map(&:y)
    zs = corners.map(&:z)

    table_length = xs.max - xs.min
    table_width = ys.max - ys.min
    table_height = zs.max

    # Calculate center of table
    center_x = xs.min + table_length / 2.0 + offset_x
    center_y = ys.min + table_width / 2.0 + offset_y

    # Create vase at origin first
    vase_group = create_vase(table_group.entities, params)

    # Move vase to table center
    move_vector = Geom::Vector3d.new(center_x, center_y, table_height)
    vase_transform = Geom::Transformation.new(move_vector)
    vase_group.transform!(vase_transform)

    # Apply material
    ceramic_material = create_ceramic_material(model)
    vase_group.material = ceramic_material

    vase_group
  end

  # Example usage with default settings
  # Orchestrates vase creation with transaction management
  #
  # @param params [Hash] Optional parameters passed to create_table_vase
  # @api orchestration
  # @return [void]
  def self.example_vase(params = {})
    model = Sketchup.active_model
    entities = model.entities

    # Configuration
    table_name = 'Table'

    # Start operation for undo/redo support
    model.start_operation('Add Vase to Table', true)

    begin
      # Find the table group
      table_group = entities.find { |e| e.is_a?(Sketchup::Group) && e.name == table_name }
      raise 'Table not found! Create a table first.' unless table_group

      # Remove old vase if exists (idempotence)
      table_group.entities.grep(Sketchup::Group).select do |g|
        g.name == 'Vase'
      end.each(&:erase!)

      # Create vase on table
      create_table_vase(table_group, params)

      # Commit the operation
      model.commit_operation

      puts 'Vase added successfully!'
      puts 'The table now has a decorative blue ceramic vase'
      puts 'Use take_screenshot() to see the updated model'
    rescue StandardError => e
      model.abort_operation
      puts "Error adding vase: #{e.message}"
      raise
    end
  end
end

if false # rubocop:disable Lint/LiteralAsCondition
  SupexSimpleTable.example_vase
end
