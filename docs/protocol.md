# Communication Protocol

Supex uses newline-delimited JSON-RPC 2.0 over local sockets.

## Transports and Ports

| Port | Transport | Channel | Purpose |
|------|-----------|---------|---------|
| `9876` | TCP | Driver/CLI <-> SketchUp runtime | Bridge tools (`tools/call`) |
| `4433` | TCP | REPL client <-> REPL server | Interactive Ruby `eval` |
| `9877` | TCP | Driver <-> VCAD sidecar | VCAD evaluation/import tooling |
| `9878` | WebSocket | Driver <-> VCAD viewer | Viewer relay/state/screenshot |

## Message Framing

- JSON-RPC 2.0 envelope
- UTF-8 encoded JSON
- One message per line (`\n`-delimited)

## Bridge Runtime (`:9876`)

### Hello Handshake

Clients identify first using `hello`.

```json
{
  "jsonrpc": "2.0",
  "method": "hello",
  "params": {
    "name": "supex-driver",
    "version": "0.2.0",
    "agent": "mcp",
    "pid": 12345,
    "token": "optional",
    "workspace": "/abs/workspace/path"
  },
  "id": "hello"
}
```

Required params: `name`, `version`, `agent`, `pid`.

### Methods

- `hello`
- `ping`
- `resources/list`
- `tools/call`

`tools/call` payload:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "eval_ruby",
    "arguments": {"code": "Sketchup.version"}
  },
  "id": 2
}
```

### Connection Lifecycle

The driver exposes a logically persistent connection and auto-reconnects on failure/idle timeout. The runtime may close a socket after non-`hello` request handling, so reconnect behavior is expected.

## REPL Server (`:4433`)

Methods are intentionally minimal:

- `hello`
- `eval`

REPL uses its own JSON-RPC loop and session snippet directory under `.tmp/repl/`.

## VCAD Sidecar (`:9877`)

Uses JSON-RPC with direct methods (`hello`, `ping`, `resources/list`) and `tools/call` for VCAD operations.

Handshake response includes negotiated protocol/capability metadata (for example: data imports, solid imports, fs watch, module tracking).

For schema contracts see:

- `docs/contracts/v1/handshake.schema.json`
- `docs/contracts/v1/tools-call.schema.json`
- `docs/contracts/v1/error-envelope.schema.json`

## Errors

Standard JSON-RPC errors apply (`-32700`, `-32600`, `-32601`, `-32602`, `-32603`).

Supex-specific conventions:

- `-32001` for authentication failures
- VCAD flows frequently return structured envelopes with `error_code` strings (for example `PATH_NOT_ALLOWED`, `PROTOCOL_MISMATCH`, `CAPABILITY_UNAVAILABLE`)

Do not rely on a single numeric code for all path-policy failures across every flow.
