# frozen_string_literal: true

require_relative 'test_helper'

class OperationTest < Minitest::Test
  class RecordingModel
    attr_reader :calls

    def initialize
      @calls = []
    end

    def start_operation(name, disable_ui = false, next_transparent = false, transparent = false)
      @calls << [:start, name, disable_ui, next_transparent, transparent]
      true
    end

    def commit_operation
      @calls << [:commit]
      true
    end

    def abort_operation
      @calls << [:abort]
      true
    end
  end

  def setup
    @model = RecordingModel.new
  end

  def test_commits_and_returns_block_value
    result = SupexStdlib::Operation.run('Build', model: @model) { |model| model.calls.length }

    assert_equal 1, result
    assert_equal [[:start, 'Build', true, false, false], [:commit]], @model.calls
  end

  def test_aborts_and_reraises_on_error
    error = assert_raises(RuntimeError) do
      SupexStdlib::Operation.run('Build', model: @model) { raise 'boom' }
    end

    assert_equal 'boom', error.message
    assert_equal [[:start, 'Build', true, false, false], [:abort]], @model.calls
  end

  def test_options_are_forwarded
    SupexStdlib::Operation.run('Tweak', model: @model, disable_ui: false, transparent: true) { nil }

    assert_equal [:start, 'Tweak', false, false, true], @model.calls.first
  end

  def test_requires_block
    assert_raises(ArgumentError) { SupexStdlib::Operation.run('Build', model: @model) }
    assert_empty @model.calls
  end

  def test_with_operation_shorthand
    result = SupexStdlib.with_operation('Shorthand', model: @model) { :done }

    assert_equal :done, result
    assert_equal [:commit], @model.calls.last
  end
end
