# frozen_string_literal: true

# Supex Extension Injector
# This script is loaded by SketchUp via -RubyStartup to inject our extension
# sources directly into the Ruby environment without copying files

verbose = ENV['SUPEX_VERBOSE'] == '1'

puts "Supex: Starting injection from '#{__dir__}'" if verbose
puts "Supex: SketchUp #{Sketchup.version}, Ruby #{RUBY_VERSION}" if verbose

# Add our extension source directory to the load path
extension_lib_path = File.expand_path('supex_runtime', __dir__)
unless $LOAD_PATH.include?(extension_lib_path)
  $LOAD_PATH.unshift(extension_lib_path)
  puts "Supex: Added '#{extension_lib_path}' to $LOAD_PATH" if verbose
end

# Add the base extension directory to load path for the main registration file
extension_base_path = __dir__
unless $LOAD_PATH.include?(extension_base_path)
  $LOAD_PATH.unshift(extension_base_path)
  puts "Supex: Added '#{extension_base_path}' to $LOAD_PATH" if verbose
end

# Show current load path for debugging
if verbose
  puts 'Supex: Current $LOAD_PATH entries:'
  $LOAD_PATH.each_with_index { |path, i| puts "  #{i}: #{path}" }
end

begin
  # Load the main extension registration file
  main_extension_file = File.join(__dir__, 'supex_runtime.rb')

  if File.exist?(main_extension_file)
    puts "Supex: Loading extension from '#{main_extension_file}'" if verbose

    # Show SketchUp console for debugging
    begin
      SKETCHUP_CONSOLE.show if verbose
    rescue
      # Console might not be available
    end

    load main_extension_file
    puts 'Supex: Extension loaded successfully'
  else
    puts "Supex: ERROR - Extension file not found at '#{main_extension_file}'"
  end
rescue StandardError => e
  puts "Supex: ERROR loading extension: #{e.message}"
  puts "Supex: Backtrace: #{e.backtrace.join("\n")}"

  # Try to show console for error visibility
  begin
    SKETCHUP_CONSOLE.show
  rescue
    # Console might not be available
  end
end
