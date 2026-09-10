# frozen_string_literal: true

module SupexRuntime
  # Binds a tool call to one specific document.
  #
  # SketchUp on macOS can keep several models open and Sketchup.active_model is the
  # one holding the focus. A caller that passes +expected_model_path+ in the tool
  # arguments asks the runtime to refuse the call unless the active model is that
  # file, so a focus change between two requests cannot redirect a mutation to
  # another document. The driver injects the argument from SUPEX_EXPECTED_MODEL.
  module TargetModel
    ARG_KEY = 'expected_model_path'

    # Raised when the active model is not the expected document
    class MismatchError < StandardError
      # @return [Hash] structured details for the JSON-RPC error envelope
      attr_reader :data

      # @param message [String]
      # @param data [Hash]
      def initialize(message, data)
        super(message)
        @data = data
      end
    end

    module_function

    # Verify that the active model is the expected document and strip the guard
    # argument before the tool sees it.
    # @param args [Hash, nil] tool arguments
    # @return [Hash, nil] arguments without +expected_model_path+
    # @raise [MismatchError] when the active model is another document or unsaved
    def enforce!(args)
      return args unless args.is_a?(Hash) && args.key?(ARG_KEY)

      expected = args[ARG_KEY].to_s
      rest = args.reject { |key, _| key == ARG_KEY }
      return rest if expected.empty?

      model = Sketchup.active_model
      actual = model ? model.path.to_s : ''
      return rest if same_file?(expected, actual)

      raise MismatchError.new(mismatch_message(expected, actual, model), mismatch_data(expected, actual, model))
    end

    # @param expected [String]
    # @param actual [String] path of the active model, empty when unsaved
    # @return [Boolean]
    def same_file?(expected, actual)
      return false if actual.empty?

      a = File.expand_path(expected)
      b = File.expand_path(actual)
      return true if a == b

      File.exist?(a) && File.exist?(b) && File.identical?(a, b)
    end

    # @return [String]
    def mismatch_message(expected, actual, model)
      current = if model.nil?
                  'no model is open'
                else
                  actual.empty? ? "the active model is unsaved (#{model.title})" : "the active model is #{actual}"
                end
      "Expected model #{File.expand_path(expected)} but #{current}; refusing to run"
    end

    # @return [Hash]
    def mismatch_data(expected, actual, model)
      {
        success: false,
        error_type: 'wrong_model',
        expected_model_path: File.expand_path(expected),
        active_model_path: actual.empty? ? nil : File.expand_path(actual),
        active_model_title: model&.title
      }
    end
  end
end
