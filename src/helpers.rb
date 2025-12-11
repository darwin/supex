# frozen_string_literal: true

# Supex Simple Table - Shared helper functions
# This module contains utility functions used across multiple scripts in this project
# Project-specific naming prevents conflicts when using multiple Supex projects

module SupexSimpleTable
  # Shared constants for attribute-based idempotence
  ATTR_DICT = 'supex'
  ATTR_KEY = 'type'

  # Per-feature identifiers (used for cleanup and material tagging)
  IDENT_TABLE = 'simple_table'
  IDENT_DECORATIONS = 'simple_table_decorations'
  IDENT_VASE = 'simple_table_vase'

  # Validates that a hash of parameters contains positive Length values
  # Raises ArgumentError with descriptive message for invalid values
  #
  # @param params [Hash] Hash of parameter name => value pairs to validate
  # @raise [ArgumentError] If any parameter is not positive
  #
  # @example Validate table dimensions
  #   validate_positive_lengths(table_length: 1.2.m, table_width: 0.8.m)
  def self.validate_positive_lengths(params)
    invalid = params.select { |_name, value| !value.is_a?(Numeric) || value <= 0 }
    return if invalid.empty?

    names = invalid.keys.map(&:to_s).join(', ')
    raise ArgumentError, "Parameters must be positive: #{names}"
  end

  # Cleanup helper for idempotent example methods
  # Removes groups by name and verifies with attributes to prevent false positives
  #
  # This function implements a two-tier cleanup approach:
  # 1. Fast name-based search to find candidate groups
  # 2. Precise attribute verification to prevent removing user's objects
  #
  # @param entities [Sketchup::Entities] Entities collection to search
  # @param name [String] Name of groups to remove
  # @param attribute_dict [String] Attribute dictionary name (e.g., 'supex')
  # @param attribute_key [String] Attribute key to verify (e.g., 'type')
  # @param attribute_value [String] Expected attribute value (e.g., 'basic_table_example')
  #
  # @example Remove previous table examples
  #   SupexSimpleTable.cleanup_by_name_and_attribute(
  #     entities, 'Table', 'supex', 'type', 'basic_table_example'
  #   )
  def self.cleanup_by_name_and_attribute(entities, name, attribute_dict, attribute_key,
                                         attribute_value)
    entities.grep(Sketchup::Group).each do |group|
      # First filter: name match (fast)
      next unless group.name == name

      # Second filter: attribute verification (precise, prevents false positives)
      group.erase! if group.get_attribute(attribute_dict, attribute_key) == attribute_value
    end
  end

  # Creates a simple material with name and color
  # Low-level material creation function
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param name [String] Name for the material
  # @param color [Sketchup::Color] Color for the material
  # @return [Sketchup::Material] The created material
  def self.create_simple_material(model, name, color)
    material = model.materials.add(name)
    material.color = color
    material
  end

  # Gets or creates a material with idempotence (check-and-reuse pattern)
  # Reuses existing material if it has our tag, otherwise creates new one
  #
  # This function implements a robust check-and-reuse approach:
  # 1. First, search for ANY material with our tag (regardless of name)
  # 2. If found -> reuse it and update color (true idempotence)
  # 3. If not found, check if requested name is available
  # 4. If name taken by user's material -> create with unique name
  # 5. If name available -> create with requested name
  #
  # @param model [Sketchup::Model] The active SketchUp model
  # @param name [String] Preferred name for the material
  # @param color [Sketchup::Color] Color for the material
  # @param tag [String] Tag value for attribute verification (e.g., 'basic_table_example')
  # @return [Sketchup::Material] The material with tag attribute
  #
  # @example Create wood material idempotently
  #   wood = SupexSimpleTable.recreate_material(
  #     model, 'Wood', Sketchup::Color.new(139, 69, 19), 'basic_table_example'
  #   )
  def self.recreate_material(model, name, color, tag)
    # First, try to find ANY existing material with our tag (regardless of name)
    tagged_material = model.materials.find { |mat| mat.get_attribute(ATTR_DICT, ATTR_KEY) == tag }

    if tagged_material
      # We already have a tagged material, reuse it (true idempotence)
      tagged_material.color = color
      return tagged_material
    end

    # No tagged material exists yet - create one
    # materials.add() automatically creates unique name if name is taken
    material = create_simple_material(model, name, color)

    # Tag it so we can find it next time (by tag, not name!)
    material.set_attribute(ATTR_DICT, ATTR_KEY, tag)

    material
  end

  # Creates a box (rectangular prism) as a group
  # Generic geometry helper for creating 3D boxes from corner coordinates
  #
  # @param entities [Sketchup::Entities] Entities collection to add box to
  # @param x1 [Length] Minimum X coordinate
  # @param y1 [Length] Minimum Y coordinate
  # @param z1 [Length] Minimum Z coordinate
  # @param x2 [Length] Maximum X coordinate
  # @param y2 [Length] Maximum Y coordinate
  # @param z2 [Length] Maximum Z coordinate
  # @return [Sketchup::Group] The created box group
  def self.create_box(entities, x1, y1, z1, x2, y2, z2)
    # Create a group for this box
    box_group = entities.add_group

    pts = [
      Geom::Point3d.new(x1, y1, z1),
      Geom::Point3d.new(x2, y1, z1),
      Geom::Point3d.new(x2, y2, z1),
      Geom::Point3d.new(x1, y2, z1)
    ]

    face = box_group.entities.add_face(pts)
    extrude_distance = z2 - z1

    # Ensure face orientation matches extrusion direction
    # Pushpull extrudes in the direction of the normal
    # If extruding up (distance > 0), normal should point up (z > 0)
    # If extruding down (distance < 0), normal should point down (z < 0)
    needs_reversal = (extrude_distance.positive? && face.normal.z.negative?) ||
                     (extrude_distance.negative? && face.normal.z.positive?)
    face.reverse! if needs_reversal

    face.pushpull(extrude_distance)

    box_group
  end

  # Takes verification screenshots of a table from multiple angles
  # Uses batch screenshots with isolate to show only the target entity
  #
  # @param entity_id [Integer] Entity ID of the group to isolate and capture
  # @param base_name [String] Base name for screenshot files (default: 'verify')
  # @return [String] Ruby code to execute via eval_ruby for taking screenshots
  #
  # @example Take screenshots of a table
  #   code = SupexSimpleTable.take_verification_screenshots_code(table.entityID, 'table')
  #   # Then execute via eval_ruby(code)
  def self.take_verification_screenshots_code(entity_id, base_name = 'verify')
    <<~RUBY
      take_batch_screenshots(
        shots: [
          { camera: { type: 'standard_view', view: 'front' }, name: '#{base_name}_front', isolate: #{entity_id} },
          { camera: { type: 'standard_view', view: 'right' }, name: '#{base_name}_right', isolate: #{entity_id} },
          { camera: { type: 'standard_view', view: 'top' }, name: '#{base_name}_top', isolate: #{entity_id} },
          { camera: { type: 'standard_view', view: 'iso' }, name: '#{base_name}_iso', isolate: #{entity_id} }
        ],
        base_name: '#{base_name}'
      )
    RUBY
  end
end
