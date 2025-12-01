# frozen_string_literal: true

require_relative 'test_helper'

class TestReplEval < Minitest::Test
  def setup
    @tester = EvalCodeTester.new
  end

  def test_eval_simple_expression
    result = @tester.eval_code('1 + 1')
    assert_equal "=> 2\n", result
  end

  def test_eval_with_puts_output
    result = @tester.eval_code('puts "hello"')
    assert_equal "hello\n=> nil\n", result
  end

  def test_eval_syntax_error
    result = @tester.eval_code('def')
    assert_match(/SyntaxError/, result)
  end

  def test_eval_name_error
    result = @tester.eval_code('NonExistentConstant')
    assert_match(/NameError/, result)
    assert_match(/NonExistentConstant/, result)
  end

  def test_eval_multiline
    code = <<~RUBY
      x = 10
      y = 20
      x + y
    RUBY
    result = @tester.eval_code(code)
    assert_equal "=> 30\n", result
  end
end
