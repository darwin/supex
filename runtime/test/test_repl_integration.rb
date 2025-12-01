# frozen_string_literal: true

require_relative 'test_helper'

# Integration tests using MockReplServer (not the actual ReplServer)
# because ReplServer depends on UI.start_timer which requires SketchUp
class TestReplIntegration < Minitest::Test
  def setup
    @mock_server = MockReplServer.new
    @mock_server.start
    @port = @mock_server.port
    @host = '127.0.0.1'
  end

  def teardown
    @mock_server.stop
  end

  def test_full_roundtrip
    # Client sends code, server evaluates and returns result
    response = ReplClientFunctions.send_to_repl('3 * 7', @host, @port)
    assert_equal "=> 21\n", response
    assert_includes @mock_server.received_messages, '3 * 7'
  end

  def test_multiple_requests
    responses = []
    codes = ['1 + 1', '2 + 2', '3 + 3']

    codes.each do |code|
      responses << ReplClientFunctions.send_to_repl(code, @host, @port)
    end

    assert_equal ["=> 2\n", "=> 4\n", "=> 6\n"], responses
    codes.each { |code| assert_includes @mock_server.received_messages, code }
  end

  def test_error_response
    @mock_server.set_response('raise "test error"', "#<RuntimeError: test error>\n")
    response = ReplClientFunctions.send_to_repl('raise "test error"', @host, @port)
    assert_match(/RuntimeError/, response)
    assert_match(/test error/, response)
  end
end
