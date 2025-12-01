# frozen_string_literal: true

require 'minitest/autorun'
require 'socket'
require 'stringio'
require 'json'
require 'fileutils'

# Test environment setup
SUPEX_NO_AUTOSTART = true
ENV['SUPEX_SILENT'] = '1'
$LOADED_FEATURES << 'sketchup.rb'
$LOADED_FEATURES << 'sketchup'

# Load mocks and helpers
require_relative 'sketchup_mocks'
require_relative 'test_servers'
require_relative 'test_utilities'

# Load runtime modules
require_relative '../../src/supex_runtime/version'
require_relative '../../src/supex_runtime/utils'
require_relative '../../src/supex_runtime/repl_server'

# Override Utils.console_write for testing (after loading the real module)
module SupexRuntime
  module Utils
    class << self
      remove_method :console_write if method_defined?(:console_write)
      attr_accessor :console_output

      def console_write(message)
        @console_output ||= []
        @console_output << message
      end

      def clear_console_output
        @console_output = []
      end
    end
  end
end
