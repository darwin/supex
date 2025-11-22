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
  def self.cleanup_by_name_and_attribute(entities, name, attribute_dict, attribute_key, attribute_value)
    entities.grep(Sketchup::Group).each do |group|
      # First filter: name match (fast)
      next unless group.name == name

      # Second filter: attribute verification (precise, prevents false positives)
      group.erase! if group.get_attribute(attribute_dict, attribute_key) == attribute_value
    end
  end
end
