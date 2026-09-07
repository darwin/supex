# frozen_string_literal: true

# Snippet Loader
# Loads all Ruby snippet files from the src/ directory into the SketchUp Ruby context.
# This file is loaded at the start of every test session; snippet files are
# loaded with `load` (not `require`) so edits take effect in a running SketchUp.

# Get the directory where this loader file is located
snippets_src_dir = File.dirname(__FILE__)

# List of snippet files to load (in dependency order if needed)
snippet_files = [
  'helpers.rb', # Load helpers first in case others depend on it
  'conftest.rb',
  'test_introspection.rb',
  'test_model_operations.rb',
  'test_error_handling.rb',
  'test_batch_screenshots.rb'
]

# Load all snippet files
snippet_files.each do |filename|
  filepath = File.join(snippets_src_dir, filename)
  if File.exist?(filepath)
    begin
      load filepath
      puts "[Snippets] Loaded: #{filename}"
    rescue StandardError => e
      puts "[Snippets] ERROR loading #{filename}: #{e.message}"
      puts e.backtrace.first(5).join("\n")
    end
  else
    puts "[Snippets] WARNING: #{filename} not found at #{filepath}"
  end
end

puts '[Snippets] All snippet files loaded successfully'
