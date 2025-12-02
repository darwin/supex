# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/repl'

# Integration tests using MockREPLServer (not the actual REPLServer)
# because REPLServer depends on UI.start_timer which requires SketchUp
class TestREPLIntegration < Minitest::Test
  def setup
    @mock_server = MockREPLServer.new
    @mock_server.start
    @port = @mock_server.port
    @host = '127.0.0.1'
  end

  def teardown
    @mock_server.stop
  end

  def test_full_roundtrip
    # Client connects, sends code, server evaluates and returns result
    client = REPLClient.new(@host, @port)
    client.connect

    response = client.eval('3 * 7')
    assert_equal "=> 21\n", response.dig('result', 'output')
    assert_includes @mock_server.received_codes, '3 * 7'

    client.close
  end

  def test_multiple_requests
    client = REPLClient.new(@host, @port)
    client.connect

    codes = ['1 + 1', '2 + 2', '3 + 3']
    responses = codes.map { |code| client.eval(code).dig('result', 'output') }

    assert_equal ["=> 2\n", "=> 4\n", "=> 6\n"], responses
    codes.each { |code| assert_includes @mock_server.received_codes, code }

    client.close
  end

  def test_error_response
    client = REPLClient.new(@host, @port)
    client.connect

    response = client.eval('raise "test error"')
    output = response.dig('result', 'output')
    assert_match(/RuntimeError/, output)
    assert_match(/test error/, output)

    client.close
  end
end
