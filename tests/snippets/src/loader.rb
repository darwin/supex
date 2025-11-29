# Snippet Loader
# Loads all Ruby snippet files from the src/ directory into the SketchUp Ruby context.
# This file should be loaded once at the start of the test session.

# Get the directory where this loader file is located
SNIPPETS_SRC_DIR = File.dirname(__FILE__)

# List of snippet files to load (in dependency order if needed)
SNIPPET_FILES = [
  'helpers.rb',              # Load helpers first in case others depend on it
  'conftest.rb',
  'test_introspection.rb',
  'test_model_operations.rb'
].freeze

# Load all snippet files
SNIPPET_FILES.each do |filename|
  filepath = File.join(SNIPPETS_SRC_DIR, filename)
  if File.exist?(filepath)
    begin
      require filepath
      puts "[Snippets] Loaded: #{filename}"
    rescue StandardError => e
      puts "[Snippets] ERROR loading #{filename}: #{e.message}"
      puts e.backtrace.first(5).join("\n")
    end
  else
    puts "[Snippets] WARNING: #{filename} not found at #{filepath}"
  end
end

puts "[Snippets] All snippet files loaded successfully"
