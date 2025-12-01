# frozen_string_literal: true

require_relative 'test_helper'

# Client functions extracted for testing
module ReplClientFunctions
  DEFAULT_PORT = 4433
  DEFAULT_HOST = '127.0.0.1'
  TIMEOUT = 5

  def self.send_to_repl(code, host, port, timeout = TIMEOUT)
    socket = Socket.new(Socket::AF_INET, Socket::SOCK_STREAM, 0)
    sockaddr = Socket.pack_sockaddr_in(port, host)

    begin
      socket.connect_nonblock(sockaddr)
    rescue Errno::EINPROGRESS
      raise Timeout::Error, 'Connection timeout' unless IO.select(nil, [socket], nil, timeout)

      begin
        socket.connect_nonblock(sockaddr)
      rescue Errno::EISCONN
        # Connected
      end
    end

    socket.write(code)
    socket.close_write
    socket.read
  rescue Errno::ECONNREFUSED
    nil
  ensure
    socket&.close
  end

  def self.server_available?(host, port)
    result = send_to_repl('1 + 1', host, port, 2)
    !result.nil?
  rescue StandardError
    false
  end
end

class TestReplClient < Minitest::Test
  def setup
    @mock_server = MockReplServer.new
    @mock_server.start
    @port = @mock_server.port
    @host = '127.0.0.1'
  end

  def teardown
    @mock_server.stop
  end

  def test_send_to_repl_success
    result = ReplClientFunctions.send_to_repl('2 + 2', @host, @port)
    assert_equal "=> 4\n", result
    assert_includes @mock_server.received_messages, '2 + 2'
  end

  def test_send_to_repl_connection_refused
    # Use a port where nothing is listening
    result = ReplClientFunctions.send_to_repl('1 + 1', @host, 59999)
    assert_nil result
  end

  def test_server_available_true
    assert ReplClientFunctions.server_available?(@host, @port)
  end

  def test_server_available_false
    # Use a port where nothing is listening
    refute ReplClientFunctions.server_available?(@host, 59999)
  end
end
