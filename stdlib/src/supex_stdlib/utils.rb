# frozen_string_literal: true

require 'sketchup'

module SupexStdlib
  # Utility functions for SketchUp model introspection
  module Utils
    # Tree symbols for ASCII output
    TREE_SYMBOLS = {
      branch: '|-- ',
      last_branch: '`-- ',
      vertical: '|   ',
      empty: '    '
    }.freeze

    # Generate a tree representation of SketchUp entity hierarchy
    # Similar to Unix `tree` command output
    #
    # @param root [Sketchup::Entities, Sketchup::Group, Sketchup::ComponentInstance, nil]
    #   Starting point for tree. Defaults to model.entities if nil.
    # @param options [Hash] Configuration options
    # @option options [Integer] :max_depth Maximum depth to traverse (nil = unlimited)
    # @option options [Boolean] :show_types Include entity type names (default: true)
    # @option options [Boolean] :show_ids Include entity IDs (default: false)
    # @option options [Boolean] :show_hidden Include hidden entities (default: false)
    # @option options [Array<String>] :types Filter to specific types (e.g., ['Group', 'ComponentInstance'])
    # @return [String] Formatted tree output
    #
    # @example Basic usage
    #   puts SupexStdlib::Utils.tree
    #   # .
    #   # |-- [Group] Table
    #   # |   |-- [Group] Top
    #   # |   `-- [Group] Legs
    #   # `-- [ComponentInstance] Chair
    #
    # @example With options
    #   puts SupexStdlib::Utils.tree(nil, max_depth: 2, show_ids: true)
    #
    def self.tree(root = nil, options = {})
      opts = {
        max_depth: nil,
        show_types: true,
        show_ids: false,
        show_hidden: false,
        types: nil
      }.merge(options)

      entities = resolve_root_entities(root)
      return "(empty)\n" if entities.nil? || entities.to_a.empty?

      lines = ['.']
      build_tree_lines(entities, lines, '', opts, 0)
      "#{lines.join("\n")}\n"
    end

    class << self
      private

      # Resolve the root to an Entities collection
      # @param root [Object, nil] The root entity or entities
      # @return [Sketchup::Entities, nil]
      def resolve_root_entities(root)
        case root
        when nil
          model = Sketchup.active_model
          model&.entities
        when Sketchup::Entities
          root
        when Sketchup::Group
          root.entities
        when Sketchup::ComponentInstance
          root.definition.entities
        end
      end

      # Recursively build tree lines
      # @param entities [Sketchup::Entities] Entities to process
      # @param lines [Array<String>] Output lines accumulator
      # @param prefix [String] Current line prefix for indentation
      # @param opts [Hash] Options hash
      # @param depth [Integer] Current depth level
      def build_tree_lines(entities, lines, prefix, opts, depth)
        return if opts[:max_depth] && depth >= opts[:max_depth]

        hierarchical = filter_entities(entities, opts)
        return if hierarchical.empty?

        hierarchical.each_with_index do |entity, index|
          is_last = (index == hierarchical.length - 1)

          branch = is_last ? TREE_SYMBOLS[:last_branch] : TREE_SYMBOLS[:branch]
          label = format_entity_label(entity, opts)
          lines << "#{prefix}#{branch}#{label}"

          child_entities = get_child_entities(entity)
          if child_entities && !child_entities.to_a.empty?
            child_prefix = prefix + (is_last ? TREE_SYMBOLS[:empty] : TREE_SYMBOLS[:vertical])
            build_tree_lines(child_entities, lines, child_prefix, opts, depth + 1)
          end
        end
      end

      # Filter entities based on options
      # @param entities [Sketchup::Entities] Source entities
      # @param opts [Hash] Options hash
      # @return [Array<Sketchup::Entity>] Filtered entities
      def filter_entities(entities, opts)
        result = entities.to_a.select do |e|
          next false unless hierarchical_entity?(e)
          next false if !opts[:show_hidden] && entity_hidden?(e)

          next false if opts[:types] && !opts[:types].include?(e.typename)

          true
        end

        result.sort_by { |e| entity_sort_key(e) }
      end

      # Check if entity is hierarchical (can contain children)
      # @param entity [Sketchup::Entity]
      # @return [Boolean]
      def hierarchical_entity?(entity)
        entity.is_a?(Sketchup::Group) || entity.is_a?(Sketchup::ComponentInstance)
      end

      # Check if entity is hidden
      # @param entity [Sketchup::Entity]
      # @return [Boolean]
      def entity_hidden?(entity)
        return false unless entity.respond_to?(:hidden?)

        entity.hidden? || (entity.respond_to?(:layer) && entity.layer && !entity.layer.visible?)
      end

      # Get sort key for entity
      # @param entity [Sketchup::Entity]
      # @return [Array] Sort key (type priority, name)
      def entity_sort_key(entity)
        type_priority = entity.is_a?(Sketchup::Group) ? 0 : 1
        name = entity_name(entity).downcase
        [type_priority, name]
      end

      # Get entity name
      # @param entity [Sketchup::Entity]
      # @return [String]
      def entity_name(entity)
        case entity
        when Sketchup::Group
          entity.name.empty? ? '(unnamed)' : entity.name
        when Sketchup::ComponentInstance
          entity.definition.name
        else
          entity.typename
        end
      end

      # Format entity label for tree output
      # @param entity [Sketchup::Entity]
      # @param opts [Hash]
      # @return [String]
      def format_entity_label(entity, opts)
        parts = []

        parts << "[#{entity.typename}]" if opts[:show_types]
        parts << entity_name(entity)
        parts << "(##{entity.entityID})" if opts[:show_ids]

        parts.join(' ')
      end

      # Get child entities from a hierarchical entity
      # @param entity [Sketchup::Entity]
      # @return [Sketchup::Entities, nil]
      def get_child_entities(entity)
        case entity
        when Sketchup::Group
          entity.entities
        when Sketchup::ComponentInstance
          entity.definition.entities
        end
      end
    end
  end
end
