# frozen_string_literal: true

# =============================================================================
# Mock Servers for Testing
# =============================================================================

# Mock TCP server for REPL client tests
class MockReplServer
  attr_reader :port, :received_messages

  def initialize(port: 0) # port 0 = auto-assign
    @server = TCPServer.new('127.0.0.1', port)
    @port = @server.addr[1]
    @received_messages = []
    @responses = {}
    @running = false
  end

  def set_response(code, response)
    @responses[code] = response
  end

  def start
    @running = true
    @thread = Thread.new do
      while @running
        begin
          client = @server.accept_nonblock
          message = client.read
          @received_messages << message
          # rubocop:disable Security/Eval
          response = @responses[message] || "=> #{eval(message).inspect}\n"
          # rubocop:enable Security/Eval
          client.write(response)
          client.close
        rescue Errno::EWOULDBLOCK, Errno::EAGAIN
          sleep 0.01
        rescue StandardError
          break unless @running
        end
      end
    end
  end

  def stop
    @running = false
    @thread&.join(1)
    @server&.close
  end
end

# Mock TCP client for BridgeServer integration tests
class MockBridgeClient
  def initialize(host: '127.0.0.1', port:)
    @host = host
    @port = port
  end

  def send_request(request)
    socket = TCPSocket.new(@host, @port)
    socket.write("#{request.to_json}\n")
    socket.flush
    response = socket.gets
    socket.close
    JSON.parse(response) if response
  rescue StandardError => e
    { 'error' => e.message }
  end

  def send_hello(name: 'test-client', version: '1.0', agent: 'test', pid: Process.pid)
    send_request({
                   'jsonrpc' => '2.0',
                   'method' => 'hello',
                   'params' => { 'name' => name, 'version' => version, 'agent' => agent, 'pid' => pid },
                   'id' => 1
                 })
  end

  def send_ping
    send_request({
                   'jsonrpc' => '2.0',
                   'method' => 'ping',
                   'id' => 2
                 })
  end

  def call_tool(name, arguments = {})
    send_request({
                   'jsonrpc' => '2.0',
                   'method' => 'tools/call',
                   'params' => { 'name' => name, 'arguments' => arguments },
                   'id' => 3
                 })
  end
end
