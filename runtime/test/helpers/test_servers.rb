# frozen_string_literal: true

# =============================================================================
# Mock Servers for Testing
# =============================================================================

# Mock TCP server for REPL client tests (JSON-RPC protocol)
class MockREPLServer
  attr_reader :port, :received_messages, :received_codes

  def initialize(port: 0) # port 0 = auto-assign
    @server = TCPServer.new('127.0.0.1', port)
    @port = @server.addr[1]
    @received_messages = []
    @received_codes = []
    @running = false
  end

  def start
    @running = true
    @thread = Thread.new do
      while @running
        begin
          client = @server.accept_nonblock
          handle_client(client)
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

  private

  def handle_client(client)
    loop do
      line = client.gets
      break unless line

      request = JSON.parse(line.strip)
      @received_messages << request
      response = handle_request(request)
      client.write("#{response.to_json}\n")
    end
  rescue JSON::ParserError, IOError
    # Client disconnected or invalid JSON
  ensure
    client&.close
  end

  def handle_request(request)
    case request['method']
    when 'hello'
      { 'jsonrpc' => '2.0', 'id' => request['id'],
        'result' => { 'success' => true, 'session' => 's000000-000000-0', 'server' => { 'name' => 'mock-repl' } } }
    when 'eval'
      code = request.dig('params', 'code')
      @received_codes << code
      output = eval_with_capture(code)
      { 'jsonrpc' => '2.0', 'id' => request['id'], 'result' => { 'output' => output, 'success' => true } }
    else
      { 'jsonrpc' => '2.0', 'id' => request['id'], 'error' => { 'code' => -32_601, 'message' => 'Method not found' } }
    end
  end

  # Evaluate code and capture result or error (like real REPL server)
  def eval_with_capture(code)
    # rubocop:disable Security/Eval
    "=> #{eval(code).inspect}\n"
    # rubocop:enable Security/Eval
  rescue StandardError => e
    "#<#{e.class}: #{e.message}>\n"
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
