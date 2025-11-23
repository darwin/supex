#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yard'
require 'fileutils'
require 'yaml'

# Generate clean Markdown documentation directly from YARD registry
# This bypasses YARD's HTML generation and HTML→Markdown conversion pipeline

OUTPUT_DIR = 'generated-sketchup-docs-md'

puts "Loading YARD registry..."
YARD::Registry.load!('.yardoc')

# Load filtering configuration
config_path = 'filter_config.yml'
if File.exist?(config_path)
  puts "Loading filter configuration from #{config_path}..."
  filter_config = YAML.load_file(config_path)
  excluded_namespaces = filter_config['excluded_namespaces'] || []
  excluded_patterns = (filter_config['excluded_patterns'] || []).map do |pattern|
    Regexp.new(pattern.gsub('*', '.*'))
  end
  puts "  Excluded namespaces: #{excluded_namespaces.join(', ')}"
  puts "  Excluded patterns: #{filter_config['excluded_patterns'].join(', ')}"
else
  puts "No filter configuration found, including all objects..."
  excluded_namespaces = []
  excluded_patterns = []
end

# Check if an object should be excluded
def should_exclude?(obj, excluded_namespaces, excluded_patterns)
  top_namespace = obj.path.split('::').first
  return true if excluded_namespaces.include?(top_namespace)
  return true if excluded_patterns.any? { |regex| regex.match?(obj.path) }
  false
end

# Format a tag value
def format_tag(tag)
  return nil unless tag
  text = tag.text.to_s.strip
  text.empty? ? nil : text
end

# Format parameter information
def format_param(param)
  parts = []
  parts << "`#{param.name}`" if param.name
  parts << "(#{param.types.join(', ')})" if param.types && !param.types.empty?
  parts << "— #{param.text}" if param.text && !param.text.strip.empty?
  parts.join(' ')
end

# Format return information
def format_return(tag)
  parts = []
  parts << "(#{tag.types.join(', ')})" if tag.types && !tag.types.empty?
  parts << "— #{tag.text}" if tag.text && !tag.text.strip.empty?
  parts.empty? ? nil : parts.join(' ')
end

# Generate Markdown for a class or module
def generate_class_markdown(obj)
  md = []

  # Header
  md << "# #{obj.type.to_s.capitalize}: #{obj.path}"
  md << ""

  # Inheritance information
  if obj.type == :class && obj.superclass && obj.superclass.path != 'Object'
    md << "**Inherits:** #{obj.superclass.path}"
    md << ""
  end

  # Overview section
  if obj.docstring && !obj.docstring.empty?
    md << "## Overview"
    md << ""
    md << obj.docstring.to_s.strip
    md << ""
  end

  # Version tag
  version_tag = obj.tag(:version)
  if version_tag
    md << "**Version:** #{format_tag(version_tag)}"
    md << ""
  end

  # Subclasses
  if obj.type == :class
    subclasses = YARD::Registry.all(:class).select { |c| c.superclass == obj }
    unless subclasses.empty?
      md << "## Direct Known Subclasses"
      md << ""
      subclasses.each { |sc| md << "- #{sc.path}" }
      md << ""
    end
  end

  # Constants
  constants = obj.constants(included: false)
  unless constants.empty?
    md << "## Constants"
    md << ""
    constants.each do |const|
      md << "### `#{const.name}`"
      md << ""
      if const.docstring && !const.docstring.empty?
        md << const.docstring.to_s.strip
        md << ""
      end
      if const.value
        md << "**Value:** `#{const.value}`"
        md << ""
      end
    end
  end

  # Class methods
  class_methods = obj.meths(scope: :class, included: false).reject { |m| m.visibility == :private }
  unless class_methods.empty?
    md << "## Class Methods"
    md << ""
    class_methods.sort_by(&:name).each do |method|
      md.concat(generate_method_markdown(method))
    end
  end

  # Instance methods
  instance_methods = obj.meths(scope: :instance, included: false).reject { |m| m.visibility == :private }
  unless instance_methods.empty?
    md << "## Instance Methods"
    md << ""
    instance_methods.sort_by(&:name).each do |method|
      md.concat(generate_method_markdown(method))
    end
  end

  md.join("\n")
end

# Generate Markdown for a method
def generate_method_markdown(method)
  md = []

  # Method signature
  sig = method.signature || "def #{method.name}"
  md << "### `#{method.name}`"
  md << ""
  md << "```ruby"
  md << sig
  md << "```"
  md << ""

  # Method description
  if method.docstring && !method.docstring.empty?
    md << method.docstring.to_s.strip
    md << ""
  end

  # Parameters
  params = method.tags(:param)
  unless params.empty?
    md << "**Parameters:**"
    md << ""
    params.each do |param|
      md << "- #{format_param(param)}"
    end
    md << ""
  end

  # Return value
  return_tags = method.tags(:return)
  unless return_tags.empty?
    md << "**Returns:**"
    md << ""
    return_tags.each do |ret|
      formatted = format_return(ret)
      md << "- #{formatted}" if formatted
    end
    md << ""
  end

  # Raises
  raises_tags = method.tags(:raise)
  unless raises_tags.empty?
    md << "**Raises:**"
    md << ""
    raises_tags.each do |raise_tag|
      types = raise_tag.types ? raise_tag.types.join(', ') : ''
      text = raise_tag.text || ''
      md << "- #{types} — #{text}".strip
    end
    md << ""
  end

  # Examples
  examples = method.tags(:example)
  unless examples.empty?
    md << "**Examples:**"
    md << ""
    examples.each do |example|
      title = example.name || "Example"
      md << "_#{title}_"
      md << ""
      md << "```ruby"
      md << example.text.strip
      md << "```"
      md << ""
    end
  end

  # Version
  version_tag = method.tag(:version)
  if version_tag
    md << "**Version:** #{format_tag(version_tag)}"
    md << ""
  end

  # See also
  see_tags = method.tags(:see)
  unless see_tags.empty?
    md << "**See also:**"
    md << ""
    see_tags.each do |see_tag|
      md << "- #{see_tag.name}"
    end
    md << ""
  end

  md << "---"
  md << ""

  md
end

# Clean output directory
puts "Cleaning output directory..."
FileUtils.rm_rf(OUTPUT_DIR)
FileUtils.mkdir_p(OUTPUT_DIR)

# Generate documentation for classes and modules
puts "Generating Markdown documentation..."

total_objects = 0
excluded_objects = 0
generated_files = 0

[:class, :module].each do |type|
  YARD::Registry.all(type).each do |obj|
    total_objects += 1

    # Skip excluded objects
    if should_exclude?(obj, excluded_namespaces, excluded_patterns)
      excluded_objects += 1
      next
    end

    # Skip objects without documentation
    next if obj.docstring.blank?

    # Generate Markdown
    markdown = generate_class_markdown(obj)

    # Determine output path (preserve namespace hierarchy)
    rel_path = obj.path.gsub('::', '/')
    md_path = File.join(OUTPUT_DIR, "#{rel_path}.md")

    # Create directory if needed
    FileUtils.mkdir_p(File.dirname(md_path))

    # Write file
    File.write(md_path, markdown)

    generated_files += 1
    puts "  ✓ #{rel_path}.md" if generated_files % 20 == 0
  end
end

puts "\n==> Markdown generation complete!"
puts "    Total objects: #{total_objects}"
puts "    Excluded: #{excluded_objects}"
puts "    Generated files: #{generated_files}"
puts "    Output: #{OUTPUT_DIR}/"
