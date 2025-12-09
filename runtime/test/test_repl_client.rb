# frozen_string_literal: true

require_relative 'helpers/test_helper'
require_relative '../src/repl'

class TestREPLClient < Minitest::Test
  def setup
    @mock_server = MockREPLServer.new
    @mock_server.start
    @port = @mock_server.port
    @host = '127.0.0.1'
  end

  def teardown
    @mock_server.stop
  end

  def test_client_connect_and_hello
    client = REPLClient.new(@host, @port)
    response = client.connect

    assert response['result']['success']
    assert_equal 's000000-000000-0', client.session
    client.close
  end

  def test_client_eval_code
    client = REPLClient.new(@host, @port)
    client.connect

    response = client.eval('2 + 2')

    assert response['result']['success']
    assert_equal "=> 4\n", response['result']['output']
    assert_includes @mock_server.received_codes, '2 + 2'
    client.close
  end

  def test_client_connection_refused
    # Use a port where nothing is listening
    client = REPLClient.new(@host, 59_999)
    assert_raises(Errno::ECONNREFUSED) { client.connect }
  end

  def test_server_available_true
    assert server_available?(@host, @port)
  end

  def test_server_available_false
    # Use a port where nothing is listening
    refute server_available?(@host, 59_999)
  end
end
