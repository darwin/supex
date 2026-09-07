# frozen_string_literal: true

module SupexStdlib
  # Transaction helper: run model edits as one undoable SketchUp operation
  module Operation
    extend self

    # Run a block inside a SketchUp operation. The operation is committed when the
    # block returns and aborted (rolled back) when it raises; the exception is re-raised.
    # Do not nest: SketchUp does not support operations inside operations.
    #
    # @param name [String] undo stack label
    # @param model [Sketchup::Model] model to edit (default: active model)
    # @param disable_ui [Boolean] skip UI updates during the operation (faster; default true)
    # @param transparent [Boolean] merge with the previous operation on the undo stack
    # @yieldparam model [Sketchup::Model] the model being edited
    # @return [Object] the block's return value
    # @raise [ArgumentError] if no block is given
    #
    # @example Move a group and return it
    #   SupexStdlib.with_operation('Move Table') do |model|
    #     group = model.find_entity_by_id(1234)
    #     group.transform!(Geom::Transformation.translation([10.cm, 0, 0]))
    #     group
    #   end
    def run(name, model: Sketchup.active_model, disable_ui: true, transparent: false)
      raise ArgumentError, 'SupexStdlib::Operation.run requires a block' unless block_given?

      model.start_operation(name, disable_ui, false, transparent)
      begin
        result = yield model
        model.commit_operation
        result
      rescue StandardError
        model.abort_operation
        raise
      end
    end
  end

  # Shorthand for {Operation.run}
  # @see Operation.run
  def self.with_operation(name, **, &)
    Operation.run(name, **, &)
  end
end
