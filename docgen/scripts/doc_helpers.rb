# frozen_string_literal: true

# Shared helper methods for documentation generation scripts

module DocHelpers
  # Convert YARD cross-references and inline code to markdown code formatting
  # Handles multiple YARD documentation formats:
  #   {#method}         -> `method`        (instance method reference)
  #   {.class_method}   -> `class_method`  (class method reference)
  #   {ClassName}       -> `ClassName`     (class/module reference)
  #   +code+            -> `code`          (inline code)
  #
  # @param text [String] Text containing YARD cross-references and inline code
  # @return [String] Text with YARD markup converted to markdown code
  def self.convert_yard_references(text)
    return text if text.nil? || text.empty?

    # Convert {ClassName}, {#method}, {.class_method} to markdown code
    # Remove leading # or . from references (YARD syntax, not part of name)
    text = text.gsub(/\{([#.]?)([^}]+)\}/, '`\2`')

    # Convert +text+ to markdown code (YARD inline code format)
    text.gsub(/\+([^+]+)\+/, '`\1`')
  end

  # Normalize text by removing line wrapping while preserving paragraph breaks
  # and intentional formatting (indented lines).
  #
  # Paragraphs are separated by blank lines (one or more empty lines)
  # Within each paragraph:
  #   - Lines without leading whitespace are joined (wrapping removed)
  #   - Lines with leading whitespace are preserved (intentional formatting)
  #
  # @param text [String] Text with possible line wrapping
  # @return [String] Text with wrapping removed but structure preserved
  def self.normalize_text(text)
    return text if text.nil? || text.empty?

    # Split by paragraph breaks (one or more blank lines)
    paragraphs = text.split(/\n\s*\n/)

    # Normalize each paragraph
    normalized = paragraphs.map do |para|
      lines = para.split("\n")

      # Remove empty lines within paragraph
      lines = lines.reject { |line| line.strip.empty? }

      result = []
      current = ''

      lines.each do |line|
        stripped = line.strip

        # Check if line has intentional formatting:
        # 1. Leading whitespace (indentation)
        # 2. Starts with list marker (-, *, +, or number followed by . or ))
        is_formatted = line =~ /^\s+/ || stripped =~ /^[-*+]|\d+[.)]/

        if is_formatted
          # Formatted line - finish current accumulated text and start new line
          result << current.strip unless current.strip.empty?
          current = stripped
        elsif current.empty?
          # Regular text - join with previous (remove wrapping)
          current = stripped
        else
          current += " #{stripped}"
        end
      end

      # Add final accumulated text
      result << current.strip unless current.strip.empty?

      result.join("\n")
    end.reject(&:empty?)

    # Join paragraphs back with double newline
    normalized.join("\n\n")
  end

  # Process YARD text: normalize line wrapping and convert YARD references
  # This is the universal helper for processing all YARD documentation text
  #
  # @param text [String] YARD documentation text
  # @return [String] Processed text ready for markdown output
  def self.process_yard_text(text)
    return text if text.nil? || text.empty?

    # First normalize (remove line wrapping, preserve paragraphs)
    normalized = normalize_text(text)
    # Then convert YARD cross-references to markdown code
    convert_yard_references(normalized)
  end
end
