# Communication Protocol

Supex uses JSON-RPC 2.0 over TCP sockets for communication between the Python driver and Ruby runtime.

## Transport

- **Protocol**: TCP sockets
- **Default port**: 9876 (Bridge), 4433 (REPL)
- **Host**: `localhost` by default
- **Framing**: Newline-delimited JSON (each message ends with `\n`)

## Message Format

All messages follow the JSON-RPC 2.0 specification.

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": { ... },
  "id": 1
}
```

### Success Response

```json
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": 1
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32000,
    "message": "Error description",
    "data": { ... }
  },
  "id": 1
}
```

## Methods

### hello

Handshake to establish connection and authenticate.

**Request**:
```json
{
  "jsonrpc": "2.0",
  "method": "hello",
  "params": {
    "name": "supex-driver",
    "version": "0.2.0",
    "agent": "claude-code",
    "pid": 12345,
    "token": "optional-auth-token"
  },
  "id": 1
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "message": "Client identified",
    "server": {
      "name": "supex-runtime",
      "version": "0.2.0"
    }
  },
  "id": 1
}
```

The `token` parameter is required when `SUPEX_AUTH_TOKEN` is set on the server.

### tools/call

Execute a tool with arguments.

**Request**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "eval_ruby",
    "arguments": {
      "code": "1 + 1"
    }
  },
  "id": 2
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "result": "2"
  },
  "id": 2
}
```

### ping

Health check (Bridge and REPL servers).

**Request**:
```json
{
  "jsonrpc": "2.0",
  "method": "ping",
  "params": {},
  "id": 3
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "ok"
  },
  "id": 3
}
```

## Error Codes

### Standard JSON-RPC Errors

| Code | Name | Description |
|------|------|-------------|
| -32700 | Parse error | Invalid JSON received |
| -32600 | Invalid request | Missing required fields |
| -32601 | Method not found | Unknown method name |
| -32602 | Invalid params | Invalid method parameters |
| -32603 | Internal error | Server-side error |

### Supex-Specific Errors

| Code | Name | Description |
|------|------|-------------|
| -32001 | Authentication failed | Invalid or missing token |
| -32002 | Path access denied | File path outside allowed roots |
| -32000 | Ruby error | Error executing Ruby code |

## Connection Lifecycle

1. **Connect**: Client opens TCP socket to server
2. **Handshake**: Client sends `hello` with agent name and optional token
3. **Operations**: Client sends `tools/call` requests
4. **Disconnect**: Client closes socket

The driver maintains a persistent connection and reuses it for multiple requests. Connection is re-established automatically after idle timeout (default 300 seconds) or on error.

## Example Session

```
Client connects to localhost:9876

Client -> Server:
{"jsonrpc":"2.0","method":"hello","params":{"name":"supex-driver","version":"0.2.0","agent":"claude-code","pid":12345},"id":1}

Server -> Client:
{"jsonrpc":"2.0","result":{"success":true,"message":"Client identified","server":{"name":"supex-runtime","version":"0.2.0"}},"id":1}

Client -> Server:
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"eval_ruby","arguments":{"code":"Sketchup.version"}},"id":2}

Server -> Client:
{"jsonrpc":"2.0","result":{"success":true,"result":"26.0.0"},"id":2}

Client closes connection
```

## Configuration

See [Configuration](configuration.md) for environment variables that affect protocol behavior:

- `SUPEX_HOST` / `SUPEX_PORT` - Server address
- `SUPEX_TIMEOUT` - Socket timeout
- `SUPEX_AUTH_TOKEN` - Authentication token
