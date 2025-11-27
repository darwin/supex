#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yard'
require 'fileutils'
require 'yaml'
require_relative 'doc_helpers'

# Build hierarchical INDEX.md for AI agents to navigate the API documentation
# Generates: Master INDEX.md -> Namespace indexes (Geom/INDEX.md, Sketchup/INDEX.md) -> Class docs

# Namespaces that get their own index file (too large for master index)
NAMESPACES_WITH_INDEX = %w[Geom Sketchup].freeze

# Category groupings for Sketchup namespace classes
SKETCHUP_CATEGORIES = {
  'Model Structure' => %w[Model Entities Selection DefinitionList RenderingOptions ShadowInfo OptionsManager OptionsProvider],
  'Geometry Primitives' => %w[Face Edge Vertex Curve ArcCurve ConstructionLine ConstructionPoint SectionPlane],
  'Containers' => %w[Group ComponentInstance ComponentDefinition Image],
  'Appearance' => %w[Material Materials Texture],
  'Organization' => %w[Layer Layers Page Pages Scenes Styles Style],
  'Annotations' => %w[Text Dimension DimensionLinear DimensionRadial],
  'Metadata' => %w[Entity Drawingelement AttributeDictionary AttributeDictionaries Classification Classifications],
  'Camera & View' => %w[Camera Axes RenderingOptions],
  'Other' => [] # Catch-all for uncategorized classes
}.freeze

# Category groupings for Geom namespace classes
GEOM_CATEGORIES = {
  'Points & Vectors' => %w[Point3d Point2d Vector3d Vector2d],
  'Transformations' => %w[Transformation Transformation2d],
  'Bounds & Meshes' => %w[BoundingBox Bounds2d OrientedBounds2d PolygonMesh],
  'Coordinates' => %w[LatLong UTM]
}.freeze

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

# Categorize classes for a namespace
def categorize_classes(classes, categories)
  categorized = Hash.new { |h, k| h[k] = [] }
  uncategorized = []

  classes.each do |cls|
    class_name = cls[:path].split('::').last
    found = false

    categories.each do |category, class_names|
      next if category == 'Other'
      if class_names.include?(class_name)
        categorized[category] << cls
        found = true
        break
      end
    end

    uncategorized << cls unless found
  end

  categorized['Other'] = uncategorized if uncategorized.any?
  categorized
end

# Generate namespace index file (e.g., Geom/INDEX.md or Sketchup/INDEX.md)
def generate_namespace_index(namespace, objects, methods_by_parent, categories)
  output_dir = "generated-sketchup-docs-md/#{namespace}"
  FileUtils.mkdir_p(output_dir)
  output_path = "#{output_dir}/INDEX.md"

  # Separate classes/modules from the main namespace object
  classes_and_modules = objects.select { |o| o[:type] == 'class' || o[:type] == 'module' }
  main_obj = classes_and_modules.find { |obj| obj[:path] == namespace }
  other_classes = classes_and_modules.reject { |obj| obj[:path] == namespace }

  File.open(output_path, 'w') do |f|
    f.puts "# #{namespace} Namespace"
    f.puts ""

    # Module description if exists
    if main_obj && !main_obj[:summary].empty?
      f.puts main_obj[:summary]
      f.puts ""
    end

    f.puts "---"
    f.puts ""

    # Module methods section
    module_methods = methods_by_parent[namespace] || []
    unless module_methods.empty?
      f.puts "## Module Methods"
      f.puts ""
      f.puts "The `#{namespace}` module provides utility methods:"
      f.puts ""
      module_methods.each do |method|
        method_name = method[:path].split(/[#.]/).last
        if method[:summary] && !method[:summary].strip.empty?
          f.puts "- `#{namespace}.#{method_name}` - #{method[:summary]}"
        else
          f.puts "- `#{namespace}.#{method_name}`"
        end
      end
      f.puts ""
      f.puts "Full module documentation: [#{namespace}.md](../#{namespace}.md)"
      f.puts ""
      f.puts "---"
      f.puts ""
    end

    # Categorize classes
    categorized = categorize_classes(other_classes, categories)

    # Output by category
    f.puts "## Classes"
    f.puts ""

    categories.keys.each do |category|
      category_classes = categorized[category]
      next unless category_classes && category_classes.any?

      f.puts "### #{category}"
      f.puts ""

      category_classes.sort_by { |c| c[:path] }.each do |cls|
        class_name = cls[:path].split('::').last
        file_path = "#{class_name}.md"
        if cls[:summary].empty?
          f.puts "- [#{class_name}](#{file_path})"
        else
          f.puts "- [#{class_name}](#{file_path}) - #{cls[:summary]}"
        end
      end

      f.puts ""
    end

  end

  puts "Generated #{output_path}"
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

# Pre-compute methods_by_parent for all namespaces (needed for namespace indexes)
all_methods_by_parent = {}
grouped_objects.each do |namespace, objects|
  methods = objects.select { |o| o[:type] == 'method' }
  methods.each do |m|
    parent = m[:path].split(/[#.]/).first
    all_methods_by_parent[parent] ||= []
    all_methods_by_parent[parent] << m
  end
end

# Generate namespace-specific index files first
puts "\nGenerating namespace indexes..."
NAMESPACES_WITH_INDEX.each do |namespace|
  next unless grouped_objects.key?(namespace)

  objects = grouped_objects[namespace].sort_by { |o| o[:path] }
  categories = namespace == 'Sketchup' ? SKETCHUP_CATEGORIES : GEOM_CATEGORIES
  generate_namespace_index(namespace, objects, all_methods_by_parent, categories)
end

# Build master INDEX.md
output_path = 'generated-sketchup-docs-md/INDEX.md'
FileUtils.mkdir_p('generated-sketchup-docs-md')

File.open(output_path, 'w') do |f|
  f.puts "# SketchUp Ruby API - Documentation Index"
  f.puts ""
  f.puts "This is a subset of the official SketchUp Ruby API documentation, filtered to include"
  f.puts "only the classes and methods relevant for 3D modeling with Supex."
  f.puts ""
  f.puts "For complete documentation, see: https://ruby.sketchup.com"
  f.puts ""
  f.puts "---"
  f.puts ""

  # Namespace listings
  sorted_namespaces.each do |namespace|
    # Special handling for Global namespace - link to TOP_LEVEL.md
    if namespace == 'Global'
      f.puts "## [Top-Level Namespace](TOP_LEVEL.md)"
      f.puts ""
      f.puts "Global constants and methods available in all SketchUp Ruby scripts."
      f.puts ""

      # List global methods with descriptions
      objects = grouped_objects[namespace].sort_by { |o| o[:path] }
      methods = objects.select { |o| o[:type] == 'method' }
      unless methods.empty?
        f.puts "**Methods:**"
        f.puts ""
        methods.each do |method|
          method_name = method[:path].split(/[#.]/).last
          if method[:summary] && !method[:summary].strip.empty?
            f.puts "- `#{method_name}` - #{method[:summary]}"
          else
            f.puts "- `#{method_name}`"
          end
        end
        f.puts ""
      end

      f.puts "Full documentation → [TOP_LEVEL.md](TOP_LEVEL.md)"
      f.puts ""
      f.puts ""
      next
    end

    # Special handling for namespaces with their own index file
    if NAMESPACES_WITH_INDEX.include?(namespace)
      objects = grouped_objects[namespace].sort_by { |o| o[:path] }
      classes_and_modules = objects.select { |o| o[:type] == 'class' || o[:type] == 'module' }
      main_obj = classes_and_modules.find { |obj| obj[:path] == namespace }
      other_classes = classes_and_modules.reject { |obj| obj[:path] == namespace }

      # Output heading with link to namespace index
      f.puts "## [#{namespace}](#{namespace}/INDEX.md) (#{main_obj ? main_obj[:type] : 'module'})"
      f.puts ""

      # Output summary if exists
      if main_obj && !main_obj[:summary].empty?
        f.puts main_obj[:summary]
        f.puts ""
      end

      # Output class count and list
      class_names = other_classes.map { |c| c[:path].split('::').last }.sort
      f.puts "**Classes (#{class_names.size}):** #{class_names.first(8).join(', ')}#{class_names.size > 8 ? ', ...' : ''}"
      f.puts ""

      # Output key module methods
      module_methods = all_methods_by_parent[namespace] || []
      unless module_methods.empty?
        method_names = module_methods.map { |m| "`#{m[:path].split(/[#.]/).last}`" }.first(6)
        f.puts "**Module methods:** #{method_names.join(', ')}"
        f.puts ""
      end

      f.puts "Full index → [#{namespace}/INDEX.md](#{namespace}/INDEX.md)"
      f.puts ""
      f.puts ""
      next
    end

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
          if method[:summary] && !method[:summary].strip.empty?
            f.puts "- `#{method_name}` - #{method[:summary]}"
          else
            f.puts "- `#{method_name}`"
          end
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
          if method[:summary] && !method[:summary].strip.empty?
            f.puts "- `#{method_name}` - #{method[:summary]}"
          else
            f.puts "- `#{method_name}`"
          end
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
        if method[:summary] && !method[:summary].strip.empty?
          f.puts "- `#{method_name}` - #{method[:summary]}"
        else
          f.puts "- `#{method_name}`"
        end
      end
      f.puts ""
    end

    f.puts ""
  end

end

puts "✓ INDEX.md generated at: #{output_path}"
