#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yard'
require 'fileutils'
require 'yaml'
require_relative 'doc_helpers'

# Build a concise INDEX.md for AI agents to navigate the API documentation

puts "Loading YARD registry..."
YARD::Registry.load!('.yardoc')

# Load filtering configuration
config_path = 'filter_config.yml'
if File.exist?(config_path)
  puts "Loading filter configuration from #{config_path}..."
  filter_config = YAML.load_file(config_path)
  excluded_namespaces = filter_config['excluded_namespaces'] || []
  excluded_patterns = (filter_config['excluded_patterns'] || []).map do |pattern|
    # Convert glob-style wildcards to regex
    # Don't anchor at end ($) so patterns match paths and their children
    # e.g., "*Observer" matches "Sketchup::AppObserver" AND "Sketchup::AppObserver#onNewModel"
    Regexp.new(pattern.gsub('*', '.*'))
  end
  puts "  Excluded namespaces: #{excluded_namespaces.join(', ')}"
  puts "  Excluded patterns: #{filter_config['excluded_patterns'].join(', ')}"
else
  puts "No filter configuration found, including all objects..."
  excluded_namespaces = []
  excluded_patterns = []
end

# Check if an object should be excluded based on filter configuration
def should_exclude?(obj, excluded_namespaces, excluded_patterns)
  # Check top-level namespace
  top_namespace = obj.path.split('::').first
  return true if excluded_namespaces.include?(top_namespace)

  # Check patterns
  return true if excluded_patterns.any? { |regex| regex.match?(obj.path) }

  false
end

# Group objects by top-level namespace
grouped_objects = Hash.new { |h, k| h[k] = [] }

# Collect all documented objects (with filtering)
total_objects = 0
excluded_objects = 0

[:class, :module, :method].each do |type|
  YARD::Registry.all(type).each do |obj|
    total_objects += 1

    # Skip undocumented objects
    next if obj.docstring.blank?

    # Skip excluded objects based on filter configuration
    if should_exclude?(obj, excluded_namespaces, excluded_patterns)
      excluded_objects += 1
      next
    end

    # Extract summary (first sentence)
    summary = obj.docstring.summary.strip
    #summary = summary[0..100] + '...' if summary.length > 100

    # Process YARD text (normalize and convert references)
    summary = DocHelpers.process_yard_text(summary)

    # Determine top-level namespace
    # For methods (Array#method or Class.method), extract the parent class/module
    # For classes/modules (Sketchup::Face), use the top-level namespace
    if obj.path.include?('#') || (obj.path.include?('.') && obj.type == :method)
      # Method: extract parent (e.g., "Array#cross" -> "Array", "Sketchup::Face#area" -> "Sketchup")
      parent_path = obj.path.split(/[#.]/).first
      path_parts = parent_path.split('::')
      namespace = path_parts.first || 'Global'
    else
      # Class/Module: use top-level namespace
      path_parts = obj.path.split('::')
      namespace = path_parts.first || 'Global'
    end

    grouped_objects[namespace] << {
      path: obj.path,
      type: type.to_s,
      summary: summary
    }
  end
end

included_objects = grouped_objects.values.flatten.size
puts "Total objects found: #{total_objects}"
puts "Excluded objects: #{excluded_objects}"
puts "Included objects: #{included_objects}"
puts "Grouped into #{grouped_objects.keys.size} namespaces"

# Sort namespaces: Global first, then alphabetically
sorted_namespaces = grouped_objects.keys.sort
sorted_namespaces = ['Global'] + (sorted_namespaces - ['Global']) if sorted_namespaces.include?('Global')

# Build INDEX.md
output_path = 'generated-sketchup-docs-md/INDEX.md'
FileUtils.mkdir_p('generated-sketchup-docs-md')

File.open(output_path, 'w') do |f|
  f.puts "# SketchUp Ruby API - Documentation Index"
  f.puts ""
  f.puts "This index provides a concise overview of the SketchUp Ruby API for AI agents."
  f.puts "Use this to quickly find relevant classes, modules, and methods before diving into detailed documentation."
  f.puts ""
  f.puts "**Included objects:** #{included_objects}"

  if excluded_objects > 0
    f.puts "**Excluded objects:** #{excluded_objects} (filtered via filter_config.yml)"
    f.puts ""
    f.puts "_Filtered namespaces:_ #{excluded_namespaces.join(', ')}" unless excluded_namespaces.empty?
  end

  f.puts ""
  f.puts "---"
  f.puts ""

  # Namespace listings
  sorted_namespaces.each do |namespace|
    # Sort objects within namespace by path
    objects = grouped_objects[namespace].sort_by { |o| o[:path] }

    # Separate classes/modules from methods
    classes_and_modules = objects.select { |o| o[:type] == 'class' || o[:type] == 'module' }
    methods = objects.select { |o| o[:type] == 'method' }

    # Group methods by their parent class/module
    methods_by_parent = methods.group_by do |m|
      # Extract parent from path (e.g., "Sketchup::Face#area" -> "Sketchup::Face")
      m[:path].split(/[#.]/).first
    end

    # Check if there's a main class/module matching the namespace name
    main_obj = classes_and_modules.find { |obj| obj[:path] == namespace }

    if main_obj
      # Include type in ## heading for main class/module
      # Add link to the actual .md file
      file_path = main_obj[:path].gsub('::', '/') + '.md'
      f.puts "## [#{namespace}](#{file_path}) (#{main_obj[:type]})"
      f.puts ""

      unless main_obj[:summary].empty?
        f.puts main_obj[:summary]
        f.puts ""
      end

      # Output methods for the main class/module
      parent_methods = methods_by_parent[main_obj[:path]] || []
      unless parent_methods.empty?
        f.puts "**Methods:**"
        f.puts ""
        parent_methods.each do |method|
          method_name = method[:path].split(/[#.]/).last
          f.puts "- `#{method_name}` - #{method[:summary]}"
        end
        f.puts ""
      end

      # Add explicit link to full documentation
      f.puts "Full documentation → [#{file_path}](#{file_path})"
      f.puts ""

      # Filter out the main object from classes_and_modules for later processing
      other_classes_and_modules = classes_and_modules.reject { |obj| obj[:path] == namespace }
    else
      # No main class/module, just output namespace heading
      f.puts "## #{namespace}"
      f.puts ""

      other_classes_and_modules = classes_and_modules
    end

    # Output other classes and modules with ### headings and their methods
    other_classes_and_modules.each do |obj|
      type_label = obj[:type]
      # Add link to the actual .md file
      file_path = obj[:path].gsub('::', '/') + '.md'
      f.puts "### [#{obj[:path]}](#{file_path}) (#{type_label})"
      f.puts ""
      unless obj[:summary].empty?
        f.puts obj[:summary]
        f.puts ""
      end

      # Output methods for this class/module as a list
      parent_methods = methods_by_parent[obj[:path]] || []
      unless parent_methods.empty?
        f.puts "**Methods:**"
        f.puts ""
        parent_methods.each do |method|
          # Extract method name (e.g., "Sketchup::Face#area" -> "area")
          method_name = method[:path].split(/[#.]/).last
          f.puts "- `#{method_name}` - #{method[:summary]}"
        end
        f.puts ""
      end

      # Add explicit link to full documentation
      f.puts "Full documentation → [#{file_path}](#{file_path})"
      f.puts ""
    end

    # Handle orphaned methods (methods without a corresponding class/module in this namespace)
    # This happens for global functions like #file_loaded, #inputbox, etc.
    class_module_paths = classes_and_modules.map { |obj| obj[:path] }
    orphaned_methods = methods.reject { |m| class_module_paths.include?(m[:path].split(/[#.]/).first) }

    unless orphaned_methods.empty?
      # Don't output heading for Global namespace (methods are already under "## Global")
      unless namespace == 'Global'
        f.puts "### Global Methods"
        f.puts ""
      end
      orphaned_methods.each do |method|
        # Extract method name (e.g., "#file_loaded" -> "file_loaded")
        method_name = method[:path].split(/[#.]/).last
        f.puts "- `#{method_name}` - #{method[:summary]}"
      end
      f.puts ""
    end

    f.puts ""
  end

  # Footer
  f.puts "---"
  f.puts ""
  f.puts "_Generated by build_index.rb from YARD documentation_"
end

puts "✓ INDEX.md generated at: #{output_path}"
