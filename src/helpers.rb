# frozen_string_literal: true

# Supex Simple Table - Shared helper functions
# This module contains utility functions used across multiple scripts in this project
# Project-specific naming prevents conflicts when using multiple Supex projects

module SupexSimpleTable
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
    tagged_material = model.materials.find { |mat| mat.get_attribute('supex', 'type') == tag }

    if tagged_material
      # We already have a tagged material, reuse it (true idempotence)
      tagged_material.color = color
      return tagged_material
    end

    # No tagged material exists yet - create one
    # materials.add() automatically creates unique name if name is taken
    material = create_simple_material(model, name, color)

    # Tag it so we can find it next time (by tag, not name!)
    material.set_attribute('supex', 'type', tag)

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

  # Moves a group to a new XY position
  # Useful for placing multiple objects side by side
  #
  # @param group [Sketchup::Group] The group to move
  # @param x [Length] X position
  # @param y [Length] Y position
  # @return [Sketchup::Group] The moved group (for chaining)
  def self.move_to(group, x, y)
    vector = Geom::Vector3d.new(x, y, 0)
    group.transform!(Geom::Transformation.new(vector))
    group
  end
end
