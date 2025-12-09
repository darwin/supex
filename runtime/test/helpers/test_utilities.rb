# frozen_string_literal: true

# =============================================================================
# Test Utilities
# =============================================================================

# Helper to extract eval_code for isolated testing
class EvalCodeTester
  def eval_code(code)
    output = StringIO.new

    with_captured_output(output) do
      # rubocop:disable Security/Eval
      result = eval(code, TOPLEVEL_BINDING)
      # rubocop:enable Security/Eval
      output.puts "=> #{result.inspect}"
    rescue Exception => e # rubocop:disable Lint/RescueException
      output.puts "#<#{e.class}: #{e.message}>"
      output.puts e.backtrace.first(5).join("\n") if e.backtrace
    end

    output.rewind
    output.read
  end

  def with_captured_output(output)
    prev_stdout = $stdout
    prev_stderr = $stderr
    $stdout = output
    $stderr = output
    yield
  ensure
    $stdout = prev_stdout
    $stderr = prev_stderr
  end
end
