#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yard'
require 'fileutils'
require 'yaml'
require_relative 'doc_helpers'

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
  if param.types && !param.types.empty?
    # Add "as" separator if we have a parameter name
    parts << "as" if param.name
    # Wrap each type in backticks
    types_formatted = param.types.map { |t| "`#{t}`" }.join(', ')
    # Only use parentheses if there's more than one type
    parts << (param.types.length > 1 ? "(#{types_formatted})" : types_formatted)
  end
  if param.text && !param.text.strip.empty?
    parts << "— #{DocHelpers.process_yard_text(param.text)}"
  end
  parts.join(' ')
end

# Format return information
def format_return(tag)
  parts = []
  if tag.types && !tag.types.empty?
    # Wrap each type in backticks
    types_formatted = tag.types.map { |t| "`#{t}`" }.join(', ')
    # Only use parentheses if there's more than one type
    parts << (tag.types.length > 1 ? "(#{types_formatted})" : types_formatted)
  end
  if tag.text && !tag.text.strip.empty?
    parts << "— #{DocHelpers.process_yard_text(tag.text)}"
  end
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
    md << "**Inherits:** `#{obj.superclass.path}`"
    md << ""
  end

  # Overview section
  if obj.docstring && !obj.docstring.empty?
    md << "## Overview"
    md << ""
    # Process YARD text (normalize and convert references)
    overview = DocHelpers.process_yard_text(obj.docstring.to_s.strip)
    md << overview
    md << ""
  end

  # Subclasses
  if obj.type == :class
    subclasses = YARD::Registry.all(:class).select { |c| c.superclass == obj }
    unless subclasses.empty?
      md << "## Direct Known Subclasses"
      md << ""
      subclasses.each { |sc| md << "- `#{sc.path}`" }
      md << ""
    end
  end

  # Constants
  constants = obj.constants(included: false)
  unless constants.empty?
    md << "## Constants"
    md << ""
    constants.each do |const|
      desc = const.docstring.to_s.strip
      # Skip useless "Stub value." descriptions
      desc = nil if desc == 'Stub value.'
      desc = DocHelpers.process_yard_text(desc) if desc && !desc.empty?

      if desc && !desc.empty?
        md << "- `#{const.name}` - #{desc}"
      else
        md << "- `#{const.name}`"
      end
    end
    md << ""
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
  md << "### #{method.name}"
  md << ""
  md << "```ruby"
  md << sig
  md << "```"
  md << ""

  # Method description
  if method.docstring && !method.docstring.empty?
    # Process YARD text (normalize and convert references)
    description = DocHelpers.process_yard_text(method.docstring.to_s.strip)
    md << description
    md << ""
  end

  # Parameters
  params = method.tags(:param)
  unless params.empty?
    md << "**Parameters:**"
    params.each do |param|
      md << "- #{format_param(param)}"
    end
    md << ""
  end

  # Return value
  return_tags = method.tags(:return)
  unless return_tags.empty?
    if return_tags.length == 1
      # Single return: compact format on one line
      formatted = format_return(return_tags.first)
      md << "**Returns:** #{formatted}" if formatted
      md << ""
    else
      # Multiple returns: use list format
      md << "**Returns:**"
      return_tags.each do |ret|
        formatted = format_return(ret)
        md << "- #{formatted}" if formatted
      end
      md << ""
    end
  end

  # Raises
  raises_tags = method.tags(:raise)
  unless raises_tags.empty?
    md << "**Raises:**"
    raises_tags.each do |raise_tag|
      if raise_tag.types && !raise_tag.types.empty?
        # Wrap each type in backticks, use parentheses only for multiple types
        types_formatted = raise_tag.types.map { |t| "`#{t}`" }.join(', ')
        types = raise_tag.types.length > 1 ? "(#{types_formatted})" : types_formatted
      else
        types = ''
      end
      if raise_tag.text
        text = DocHelpers.process_yard_text(raise_tag.text)
      else
        text = ''
      end
      md << "- #{types} — #{text}".strip
    end
    md << ""
  end

  # Examples
  examples = method.tags(:example)
  unless examples.empty?
    md << "**Examples:**"
    examples.each do |example|
      # Only output title if it's meaningful (not empty, not default "Example")
      if example.name && !example.name.strip.empty? && example.name.strip != "Example"
        md << "_#{example.name}_"
        md << ""
      end
      md << "```ruby"
      md << example.text.strip
      md << "```"
      md << ""
    end
  end

  # See also
  see_tags = method.tags(:see)
  unless see_tags.empty?
    md << "**See also:**"
    see_tags.each do |see_tag|
      ref = see_tag.name.to_s.strip
      # Convert #method or .method to anchor link
      if ref.start_with?('#', '.')
        method_name = ref[1..-1]  # Remove leading # or .
        # GitHub-flavored markdown removes special chars from anchors
        anchor = method_name.gsub(/[^a-zA-Z0-9_-]/, '')
        md << "- [#{method_name}](##{anchor})"
      else
        md << "- #{DocHelpers.convert_yard_references(ref)}"
      end
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

# Process extra pages (guides, tutorials, etc.)
included_pages = filter_config['included_pages'] || []

if included_pages.any?
  puts "\nProcessing extra pages..."
  pages_dir = File.join(OUTPUT_DIR, 'pages')
  FileUtils.mkdir_p(pages_dir)

  pages_generated = 0

  included_pages.each do |page_name|
    source_path = "sketchup-api-stubs/pages/#{page_name}.md"

    unless File.exist?(source_path)
      puts "  ✗ #{page_name}.md not found at #{source_path}"
      next
    end

    content = File.read(source_path)

    # Extract title from @title directive (e.g., "# @title Generating Geometry")
    title = page_name.gsub('_', ' ').split.map(&:capitalize).join(' ')
    if content =~ /^#\s*@title\s+(.+)$/
      title = $1.strip
      # Remove the @title line from content
      content = content.sub(/^#\s*@title\s+.+\n?/, '')
    end

    # Add proper markdown header
    processed = "# #{title}\n\n"

    # Process the content line by line to handle special cases
    content.each_line do |line|
      # Convert !!!lang code block hints to standard markdown
      # e.g., "!!!cpp" at start of code block becomes "cpp" language hint
      if line =~ /^```(\S*)$/
        processed << line
      elsif line =~ /^!!!(\w+)$/
        # This is a language hint inside a code block, skip it
        # The next code block will use this language
        next
      else
        processed << line
      end
    end

    # Process YARD cross-references
    processed = DocHelpers.convert_yard_references(processed)

    # Convert underscores to hyphens for URI-friendly output filename
    output_name = page_name.gsub('_', '-')
    output_path = File.join(pages_dir, "#{output_name}.md")
    File.write(output_path, processed)

    pages_generated += 1
    puts "  ✓ pages/#{output_name}.md"
  end

  puts "\n==> Extra pages complete!"
  puts "    Generated: #{pages_generated}"
end

# Generate TOP-LEVEL.md
puts "\nGenerating top-level namespace documentation..."

# Load constant exclusion patterns
excluded_constant_patterns = (filter_config['excluded_constant_patterns'] || []).map do |pattern|
  Regexp.new("^#{pattern.gsub('*', '.*')}$")
end

# Check if a constant should be excluded
def should_exclude_constant?(const_name, excluded_constant_patterns)
  excluded_constant_patterns.any? { |regex| regex.match?(const_name.to_s) }
end

# Get root namespace
root = YARD::Registry.root

# Collect root-level constants (not inside any class/module)
root_constants = YARD::Registry.all(:constant).select do |const|
  # Only include constants at root level (no :: in path, or path equals name)
  const.path == const.name.to_s
end

# Filter constants
filtered_constants = root_constants.reject do |const|
  should_exclude_constant?(const.name, excluded_constant_patterns)
end

# Group constants by category
constant_categories = {
  'Geometry' => %w[ORIGIN ORIGIN_2D X_AXIS Y_AXIS Z_AXIS X_AXIS_2D Y_AXIS_2D IDENTITY IDENTITY_2D],
  'Layer Visibility' => /^LAYER_/,
  'Page/Scene Flags' => /^PAGE_/,
  'File Operations' => /^FILE_WRITE_/
}

categorized_constants = {}
uncategorized_constants = []

filtered_constants.each do |const|
  categorized = false
  constant_categories.each do |category, matcher|
    if matcher.is_a?(Array)
      if matcher.include?(const.name.to_s)
        categorized_constants[category] ||= []
        categorized_constants[category] << const
        categorized = true
        break
      end
    elsif matcher.is_a?(Regexp)
      if matcher.match?(const.name.to_s)
        categorized_constants[category] ||= []
        categorized_constants[category] << const
        categorized = true
        break
      end
    end
  end
  uncategorized_constants << const unless categorized
end

# Get root-level methods
root_methods = YARD::Registry.all(:method).select do |method|
  # Root methods have paths like "#method_name"
  method.path.start_with?('#')
end

# Build the markdown
md = []
md << "# Top-Level Namespace"
md << ""
md << "Global constants and methods available in SketchUp Ruby scripts."
md << ""

# Constants section
if filtered_constants.any?
  md << "## Constants"
  md << ""

  # Output categorized constants first
  constant_categories.keys.each do |category|
    constants = categorized_constants[category]
    next unless constants && constants.any?

    md << "### #{category}"
    md << ""
    constants.sort_by(&:name).each do |const|
      desc = const.docstring.to_s.strip
      desc = desc.split("\n").first if desc # Take first line only
      desc = DocHelpers.process_yard_text(desc) if desc && !desc.empty?
      if desc && !desc.empty?
        md << "- `#{const.name}` — #{desc}"
      else
        md << "- `#{const.name}`"
      end
    end
    md << ""
  end

  # Output uncategorized constants
  if uncategorized_constants.any?
    md << "### Other Constants"
    md << ""
    uncategorized_constants.sort_by(&:name).each do |const|
      desc = const.docstring.to_s.strip
      desc = desc.split("\n").first if desc
      desc = DocHelpers.process_yard_text(desc) if desc && !desc.empty?
      if desc && !desc.empty?
        md << "- `#{const.name}` — #{desc}"
      else
        md << "- `#{const.name}`"
      end
    end
    md << ""
  end
end

# Methods section
if root_methods.any?
  md << "## Methods"
  md << ""

  root_methods.sort_by(&:name).each do |method|
    md.concat(generate_method_markdown(method))
  end
end

# Write the file
output_path = File.join(OUTPUT_DIR, 'TOP-LEVEL.md')
File.write(output_path, md.join("\n"))

puts "  ✓ TOP-LEVEL.md"
puts "    Constants: #{filtered_constants.size} (#{root_constants.size - filtered_constants.size} excluded)"
puts "    Methods: #{root_methods.size}"
