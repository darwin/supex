# frozen_string_literal: true

# Platform utilities adapted from tt-lib by Thomas Thomassen (MIT License).
# https://github.com/thomthom/tt-lib

return if defined?(SupexStdlib::Platform)

module SupexStdlib
  # Platform detection and system information utilities.
  #
  # Provides methods and constants for determining the current platform
  # (macOS or Windows) and architecture (32 or 64 bit).
  #
  # @example
  #   if SupexStdlib::Platform.mac?
  #     puts "Running on macOS"
  #   end
  #
  #   puts SupexStdlib::Platform::ID  # => "osx64" or "win64"
  module Platform
    class << self
      # Check if running on macOS.
      #
      # @return [Boolean] true if running on macOS
      def mac?
        Sketchup.platform == :platform_osx
      end

      # Check if running on Windows.
      #
      # @return [Boolean] true if running on Windows
      def win?
        Sketchup.platform == :platform_win
      end

      # Find the system temporary directory.
      #
      # Checks multiple sources in order:
      # 1. Sketchup.temp_dir
      # 2. TMPDIR environment variable
      # 3. TMP environment variable
      # 4. TEMP environment variable
      #
      # @return [String] expanded path to temp directory
      # @raise [RuntimeError] if no temp directory can be found
      def temp_path
        paths = [
          Sketchup.temp_dir,
          ENV.fetch('TMPDIR', nil),
          ENV.fetch('TMP', nil),
          ENV.fetch('TEMP', nil)
        ]
        temp = paths.find { |path| path && File.exist?(path) }
        raise 'Unable to locate temp directory' if temp.nil?

        File.expand_path(temp)
      end
    end

    # Architecture pointer size in bits (32 or 64).
    #
    # @return [Integer] 32 or 64
    POINTER_SIZE = ['a'].pack('P').size * 8

    # Platform key for selecting platform-specific resources.
    #
    # @return [String] 'osx' on macOS, 'win' on Windows
    KEY = (mac? ? 'osx' : 'win').freeze

    # Full platform identifier combining KEY and POINTER_SIZE.
    #
    # @return [String] e.g., 'osx64', 'win64'
    ID = "#{KEY}#{POINTER_SIZE}".freeze

    # Human-readable platform name.
    #
    # @return [String] 'macOS' or 'Windows'
    NAME = (mac? ? 'macOS' : 'Windows').freeze

    # Boolean flag for macOS.
    #
    # @return [Boolean] true if running on macOS
    IS_MAC = mac?

    # Boolean flag for Windows.
    #
    # @return [Boolean] true if running on Windows
    IS_WIN = win?
  end
end
